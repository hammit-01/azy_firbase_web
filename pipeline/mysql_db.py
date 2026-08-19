"""MySQL 연결 및 공통 쿼리 유틸리티."""
import os
import re
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from dbutils.pooled_db import PooledDB

_PASSWORD = os.environ.get("MYSQL_PASSWORD")
if not _PASSWORD:
    raise RuntimeError(
        "MYSQL_PASSWORD 환경변수가 설정되지 않았습니다. "
        "(로컬 실행: setx MYSQL_PASSWORD ... 후 새 터미널 / 서비스: NSSM AppEnvironmentExtra에 등록)"
    )

_CONFIG = {
    "host":    os.environ.get("MYSQL_HOST", "localhost"),
    "user":    os.environ.get("MYSQL_USER", "hyemi"),
    "password": _PASSWORD,
    "database": os.environ.get("MYSQL_DATABASE", "azy_warehouse"),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

# 파이프라인(1분 간격, 사이클당 5~6회 연결)과 API 서버(요청마다 연결)가
# 매번 새 TCP+인증 핸드셰이크를 여는 대신 커넥션을 재사용한다.
# ping=1(PING_CHECK)로 매 대여 전에 살아있는지 확인 후 죽었으면 재연결 —
# 평일 08~17시만 돌아서 주말 새벽엔 커넥션이 MySQL wait_timeout보다
# 오래 idle 상태로 남기 때문에 필요.
_pool = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=1,
    maxcached=5,
    blocking=True,
    ping=1,
    **_CONFIG,
)

@contextmanager
def get_conn():
    conn = _pool.connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_INT_COLS   = {"재고", "holdingTotal", "원본재고", "stock_version"}
_FLOAT_COLS = {"평중", "중량"}

def _val(col, row):
    v = row.get(col)
    if col in _INT_COLS:
        try: return int(v or 0)
        except: return 0
    if col in _FLOAT_COLS:
        try: return float(v) if v not in (None, "", "nan", "NaN") else None
        except: return None
    return v if v is not None else ""


def sync_freeze(row: dict) -> dict:
    """상품명과 상태(freeze/동결)를 서로 맞춘다.
    상품명에 "동결"이 있으면 상태를 freeze로, 상태가 freeze면 상품명 앞에 "동결"을 붙인다.
    단, 홀딩(holding) 중이면 건드리지 않음 — 사용자가 직접 건 홀딩이 자동 동결
    재적용보다 우선해야 하는데, 예전엔 이 구분이 없어서 동결 상품을 홀딩해도
    다음 파이프라인 사이클에 상태가 다시 freeze로 되돌아갔다(2026-08-03 발견)."""
    name = str(row.get("상품명") or "").strip()
    if row.get("상태") == "holding":
        return row
    if "동결" in name:
        if row.get("상태") != "freeze":
            row["상태"] = "freeze"
    elif row.get("상태") == "freeze" and name:
        row["상품명"] = f"동결 {name}"
    return row


_ESTNO_DIGIT_RE = re.compile(r'^\d+$')

# (상품명/브랜드 조건, 고정 ESTNO) — 원본 ESTNO가 비어있든 숫자든 무조건 이 값으로 덮어씀
_ESTNO_FORCE_RULES = [
    (lambda row: row.get("상품명") == "곱창" and row.get("브랜드") == "AMP", "ME103"),
]

# (상품명/브랜드 조건, 붙일 접두어) — ESTNO가 순수 숫자일 때만 적용
_ESTNO_PREFIX_RULES = [
    (lambda row: row.get("상품명") in ("닭장각", "닭장각정육"), "SIF"),
    (lambda row: row.get("상품명") == "안창살" and row.get("브랜드") == "GREENLEA", "ME"),
]

# 조건 만족 시 해당 행을 아예 저장하지 않음(신규 삽입 차단) — 기존에 이미 들어간 행은
# 별도로 직접 DELETE 필요(이 필터는 앞으로 다시 안 들어오게만 막음)
# (2026-07-29에 돈목뼈/SWIFT 특정 이상 배치 하나를 막으려고 상품명+브랜드로 걸었다가,
# 2026-08-03에 같은 조건의 정상 신규 입고분(BL=ONEYRICGS0272500, 133개)까지
# 통째로 막아버린 사고 발견 — 규칙 삭제. 앞으로 비슷한 요청이 오면 반드시 BL/ESTNO
# 등 그 배치만 특정할 수 있는 조건으로 좁혀서 걸 것, 상품명+브랜드처럼 넓은 조건 금지)
_EXCLUDE_RULES = []

def is_excluded(row: dict) -> bool:
    return any(cond(row) for cond in _EXCLUDE_RULES)


# (조건, 새 상품명) — 조건 만족 시 상품명을 강제로 바꿔치기
_NAME_RENAME_RULES = [
    # KILCOY만 사내 표기가 원본과 다름(2026-08-12 확인) — 브랜드 조건 없이 걸려있어서
    # AMH의 양지OFF까지 같이 양지ON으로 잘못 바뀌던 걸 KILCOY로 좁힘.
    (lambda row: row.get("상품명") == "양지OFF" and row.get("브랜드") == "KILCOY" and str(row.get("창고") or "").startswith("곤"), "양지ON"),
]

def sync_name_rename(row: dict) -> dict:
    for condition, new_name in _NAME_RENAME_RULES:
        if condition(row):
            row["상품명"] = new_name
            break
    return row


# 조건 만족 시 등급을 비움 — 돈목뼈/SWIFT는 사이트 원본이 등급 자리에 중량 코드를 줌
_GRADE_CLEAR_RULES = [
    lambda row: row.get("상품명") == "돈목뼈" and row.get("브랜드") == "SWIFT" and row.get("등급") == "15.88KG",
]

def sync_grade_clear(row: dict) -> dict:
    for condition in _GRADE_CLEAR_RULES:
        if condition(row):
            row["등급"] = ""
            break
    return row


# (조건, {필드: 값}) — 조건 만족 시 비어있는 필드만 채움(이미 값 있으면 안 건드림).
# BL로 좁혀서 건다 — 상품명만으로 걸면 다른 브랜드의 동명 상품까지 잘못 덮어씀
# (2026-07-29 돈목뼈/SWIFT 전체 제외 사고와 같은 실수 반복 방지).
_FIELD_FILL_RULES = [
    (lambda row: row.get("BL") == "HLCUSYD251245191", {"브랜드": "MERAMIST", "등급": "A", "ESTNO": "3416"}),
]

def sync_field_fill(row: dict) -> dict:
    for condition, fields in _FIELD_FILL_RULES:
        if condition(row):
            for f, v in fields.items():
                if not str(row.get(f) or "").strip():
                    row[f] = v
            break
    return row


def sync_estno_prefix(row: dict) -> dict:
    """상품명/브랜드 조합에 따라 ESTNO를 고정값으로 맞추거나(FORCE),
    원본이 순수 숫자일 때만 정해진 접두어를 붙인다(PREFIX)."""
    for condition, value in _ESTNO_FORCE_RULES:
        if condition(row):
            row["ESTNO"] = value
            return row

    estno = str(row.get("ESTNO") or "").strip()
    if not estno or not _ESTNO_DIGIT_RE.match(estno):
        return row
    for condition, prefix in _ESTNO_PREFIX_RULES:
        if condition(row):
            row["ESTNO"] = prefix + estno
            break
    return row


def upsert_inventory(conn, rows: list[dict]):
    """inventory 테이블 upsert (INSERT ... ON DUPLICATE KEY UPDATE)."""
    rows = [r for r in rows if not is_excluded(r)]
    if not rows:
        return
    cols = ["id","pk","상품명","브랜드","등급","ESTNO","재고","BL","창고",
            "유통기한","중량","평중","출고일","홀딩","상태","메모","수집일",
            "holdingTotal","holdingRecordId","이상","원본재고","stock_version"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO inventory ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        data = [[_val(c, sync_field_fill(sync_grade_clear(sync_name_rename(sync_estno_prefix(sync_freeze(row)))))) for c in cols] for row in rows]
        cur.executemany(sql, data)


def delete_inventory(conn, ids: list[str]):
    if not ids:
        return
    placeholders = ", ".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM inventory WHERE id IN ({placeholders})", ids)


_HR_INT_COLS = {"수량"}

def _hr_val(col, rec):
    v = rec.get(col)
    if col in _HR_INT_COLS:
        try: return int(v or 0)
        except: return 0
    return v if v is not None else ""


def upsert_holding_record(conn, rec: dict):
    cols = ["id","pk","BL","ESTNO","등급","수량","홀딩","출고일","메모","uid","홀딩일자"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO holding_records ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        cur.execute(sql, [_hr_val(c, rec) for c in cols])


def delete_holding_record(conn, rec_id: str):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM holding_records WHERE id=%s", (rec_id,))


def get_holding_sum(conn) -> dict:
    """pk → ACTIVE 예약 수량 합계 (holding_records 기준)."""
    with conn.cursor() as cur:
        cur.execute("SELECT pk, SUM(수량) as total FROM holding_records WHERE pk != '' AND status='ACTIVE' GROUP BY pk")
        return {row["pk"]: int(row["total"] or 0) for row in cur.fetchall()}


def get_holding_records_by_key(conn) -> dict:
    """(BL, ESTNO, 등급) → [record] 인덱스."""
    result = {}
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM holding_records WHERE BL != ''")
        for row in cur.fetchall():
            key = (row["BL"], row["ESTNO"], row["등급"])
            result.setdefault(key, []).append({
                "id":    row["id"],
                "pk":    row["pk"],
                "qty":   int(row["수량"] or 0),
                "출고일": row["출고일"] or "",
                "홀딩":   row["홀딩"] or "",
            })
    return result


def get_holding_rows_by_bl(conn) -> dict:
    """BL → [holding row] 인덱스 (inventory 홀딩행 기준)."""
    result = {}
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM inventory WHERE 수집일='' AND 상태='holding' AND BL!=''")
        for row in cur.fetchall():
            bl = row["BL"]
            result.setdefault(bl, []).append({
                "doc_id":          row["id"],
                "pk":              row["pk"] or "",
                "estno":           row["ESTNO"] or "",
                "grade":           row["등급"] or "",
                "qty":             int(row["재고"] or 0),
                "holdingRecordId": row["holdingRecordId"] or "",
                "출고일":          row["출고일"] or "",
                "홀딩":            row["홀딩"] or "",
            })
    return result


def get_snapshot(conn) -> dict:
    """현재 inventory 크롤행 → prev_snapshot 형식으로 반환."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM inventory WHERE 수집일 != ''")
        return {row["id"]: dict(row) for row in cur.fetchall()}


# ── 타창고(azy) 전용 함수 ─────────────────────────────────────

def upsert_azy_inventory(conn, rows: list[dict]):
    rows = [r for r in rows if not is_excluded(r)]
    if not rows:
        return
    cols = ["id","pk","상품명","브랜드","등급","ESTNO","재고","BL","창고",
            "유통기한","중량","평중","출고일","홀딩","상태","메모","수집일",
            "holdingTotal","holdingRecordId","이상","원본재고","stock_version"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO azy_inventory ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        data = [[_val(c, sync_field_fill(sync_grade_clear(sync_name_rename(sync_estno_prefix(sync_freeze(row)))))) for c in cols] for row in rows]
        cur.executemany(sql, data)


def delete_azy_inventory(conn, ids: list[str]):
    if not ids:
        return
    placeholders = ", ".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM azy_inventory WHERE id IN ({placeholders})", ids)


def snapshot_daily(conn):
    """하루 마감 시점(평일 17:10)의 inventory/azy_inventory를 yesterday_* 테이블로
    통째로 복사(교체) — 업데이트 탭이 다음날 "어제 대비 뭐가 바뀌었나"를 비교하는 기준.
    inventory/azy_inventory 원본은 절대 건드리지 않는다(홀딩/동결/마스터필드 보존 상태가
    거기 계속 살아있어야 함).

    주의: SELECT *라서 inventory/azy_inventory에 컬럼을 추가하면 yesterday_*에도 반드시
    같이 추가해야 함 — 안 그러면 "Column count doesn't match"로 매일 조용히 실패하고
    (예외는 run_daily_snapshot()이 로그만 남기고 삼킴) yesterday_* 테이블이 텅 비어서
    업데이트 탭이 전 품목을 "신규"로 오판정한다(2026-08-06, stock_version 추가 때 이
    테이블들을 빠뜨려서 실제로 겪은 사고)."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE yesterday_inventory")
        cur.execute("INSERT INTO yesterday_inventory SELECT * FROM inventory")
        cur.execute("TRUNCATE TABLE yesterday_azy_inventory")
        cur.execute("INSERT INTO yesterday_azy_inventory SELECT * FROM azy_inventory")


def sync_moving_inventory(conn, rows: list[dict]):
    """이고(창고이동) 취합 시트 → moving_inventory 통째로 교체.
    이 테이블은 '오늘' 상태만 보여주는 용도라 매 사이클 전체 삭제 후 다시 채운다."""
    cols = ["id", "상품명", "브랜드", "등급", "ESTNO", "재고", "BL", "이력번호", "출고창고", "이동창고"]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM moving_inventory")
        if rows:
            placeholders = ", ".join(["%s"] * len(cols))
            col_names    = ", ".join([f"`{c}`" for c in cols])
            sql = f"INSERT INTO moving_inventory ({col_names}) VALUES ({placeholders})"
            data = [[row.get(c, "") for c in cols] for row in rows]
            cur.executemany(sql, data)


def _table_for_warehouse(warehouse: str) -> str:
    # JNS(제니스) 하위창고는 전부 "곤" 접두 — inventory 테이블, 그 외 타창고는 azy_inventory
    return "inventory" if str(warehouse or "").startswith("곤") else "azy_inventory"


def apply_moving_deductions(conn, moving_rows: list[dict], deduct_targets=("inventory", "azy_inventory"),
                             deduct_warehouses=None) -> list[dict]:
    """moving_inventory 행을 상품명/브랜드/등급/ESTNO/BL 기준으로 처리한다.

    1) 이동창고(도착지) 쪽 재고가 "어제 마감 대비" 이고 수량만큼 늘어나 있으면
       "입고 완료"로 보고 이 행을 결과에서 제외한다 (호출부가 moving_inventory에서
       빼는 데 씀 — 이고분 취합 시트 체크박스가 안 풀려도 우리 쪽 표시에선 사라짐).
       절대 수량만 보면(예: 도착지에 같은 상품/BL이 이동 전부터 이미 이고 수량만큼
       있던 경우) 이동이 시작되기도 전에 "입고 완료"로 오판정한다 — 그래서 어제
       마감 스냅샷(yesterday_inventory/yesterday_azy_inventory)을 기준선으로 두고
       "지금 - 어제" 증가분만 비교한다(2026-07-31, 실사용 중 오판정 사례로 발견).
       입고 감지는 항상 양쪽 테이블 다 본다 (어느 쪽으로 입고되든 감지해야 함).
    2) 아직 미입고인 나머지 행은 출고창고(곤 접두 → inventory, 그 외 → azy_inventory)의
       매칭 재고에서 이고 수량만큼 뺀다 — 홀딩과 동일하게 매 사이클 다시 계산되는
       방식이라 별도 이력 테이블 없이 여기서 매번 다시 적용한다.

       inventory(JNS)와 azy_inventory는 서로 다른 독립 스케줄(run_jns_pipeline/
       run_pipeline)에서 각자 크롤 원본으로 재고를 통째로 덮어쓴다. 두 잡이 매번
       양쪽 다 차감해버리면, 자기 테이블이 아직 안 갱신된 사이클에 남의 차감을
       또 빼서 이중 차감되거나, 반대로 상대 잡이 방금 원본으로 덮어써서 차감이
       지워진 채로 남는다. deduct_targets로 "이번 호출에서 내가 방금 원본을
       갱신한 테이블"만 차감하도록 호출부(run_pipeline/run_jns_pipeline)가 범위를
       좁힌다.

       azy_inventory는 이 문제가 테이블 단위보다 더 세분화된다 — 에이스(에이스기흥/
       처인/용인)는 run_ace_pipeline이 1시간에 한 번만 원본을 갱신하는데, 일반
       run_pipeline은 azy_inventory 전체를 대상으로 1분마다 이 함수를 부른다. 그러면
       에이스 창고 행은 원본이 그대로인 1시간 동안 1분마다 계속 차감을 반복 적용해
       버려서 재고가 순식간에 0까지 떨어진다(2026-08-03, 실사용 중 발견). deduct_warehouses
       로 "이번 호출에서 내가 방금 원본을 갱신한 창고"만 차감하도록 추가로 좁힌다
       (None이면 deduct_targets 범위 내 전체 창고 — 기존 동작 그대로).

    반환값: 아직 미입고라 moving_inventory에 그대로 남겨야 하는 행 목록.
    """
    def _row_where(row, warehouse):
        """BL을 미리 알 수 없는 "출고분" 이고 항목은 row["이력번호"](수정사항 열, 뒤
        4자리)가 채워져 있다 — 이 경우 BL 대신 상품명/브랜드/등급/ESTNO+창고에 더해
        id에 그 이력번호가 포함되는지로 매칭한다(2026-08-04, 사용자 설명으로 도입).
        평소(BL 있음)엔 기존처럼 BL로 매칭."""
        base_cols = ("상품명", "브랜드", "등급", "ESTNO")
        where = " AND ".join(f"{c}=%s" for c in base_cols) + " AND 창고=%s"
        params = tuple(row[c] for c in base_cols) + (warehouse,)
        if row.get("이력번호"):
            where += " AND id LIKE %s"
            params += (f"%_{row['이력번호']}_%",)
        else:
            where += " AND BL=%s"
            params += (row["BL"],)
        return where, params

    def _matched_qty(cur, table, row, warehouse):
        where, params = _row_where(row, warehouse)
        cur.execute(f"SELECT COALESCE(SUM(재고), 0) AS qty FROM {table} WHERE {where}", params)
        return int(cur.fetchone()["qty"] or 0)

    def _new_lot_arrived(cur, table, yesterday_table, row, warehouse):
        """어제는 없었는데 오늘 새로 생긴 로트(유통기한까지 포함된 id)가 이고 수량
        이상이면 그 자체로 입고 완료로 본다. 합계 기준 비교(arrived_qty)만 쓰면,
        같은 BL을 쓰는 다른 무관한 로트가 이 이고와 별개로 같은 시기에 줄어들 때
        그 감소분이 실제 입고분을 상쇄해서 놓치는 경우가 있다(2026-08-04, 실사용
        중 발견 — 삼겹양지/EXCEL/UN/86E: 83개 새 로트가 정확히 도착했는데 기존
        다른 로트가 3개 줄어서 순증가가 80으로 계산돼 미입고로 오판정)."""
        where, params = _row_where(row, warehouse)
        cur.execute(f"SELECT id, 재고 FROM {table} WHERE {where}", params)
        now_rows = cur.fetchall()
        cur.execute(f"SELECT id FROM {yesterday_table} WHERE {where}", params)
        yesterday_ids = {r["id"] for r in cur.fetchall()}
        return any(r["id"] not in yesterday_ids and (r["재고"] or 0) >= row["재고"] for r in now_rows)

    _YESTERDAY_TABLE = {"inventory": "yesterday_inventory", "azy_inventory": "yesterday_azy_inventory"}

    remaining = []
    with conn.cursor() as cur:
        for row in moving_rows:
            dest_table = _table_for_warehouse(row["이동창고"])
            arrived_qty  = _matched_qty(cur, dest_table, row, row["이동창고"])
            baseline_qty = _matched_qty(cur, _YESTERDAY_TABLE[dest_table], row, row["이동창고"])
            if arrived_qty >= baseline_qty + row["재고"]:
                continue  # 어제보다 이고 수량만큼 늘었음 — 입고 완료, 더 이상 표시 안 함
            if _new_lot_arrived(cur, dest_table, _YESTERDAY_TABLE[dest_table], row, row["이동창고"]):
                continue  # 어제 없던 새 로트가 이고 수량 이상으로 생김 — 입고 완료
            remaining.append(row)

        for row in remaining:
            src_table = _table_for_warehouse(row["출고창고"])
            if src_table not in deduct_targets:
                continue
            if deduct_warehouses is not None and row["출고창고"] not in deduct_warehouses:
                continue
            where, where_params = _row_where(row, row["출고창고"])
            params = (row["재고"],) + where_params
            cur.execute(
                f"UPDATE {src_table} SET 재고 = GREATEST(재고 - %s, 0) WHERE {where}",
                params,
            )

    return remaining


def create_reservation(conn, product: dict) -> dict:
    """예약(홀딩) 생성 — 실재고와 예약을 분리하는 새 모델(2026-08-05 재설계).

    기존 apply_holding_sheet()와 달리 소스 재고(실재고)는 절대 건드리지 않는다 —
    크롤러만 실재고를 갱신하고, 예약은 holding_records/azy_holding_records에만
    쌓인다. 가용재고는 API 조회 시점에 "실재고 − ACTIVE 예약 합계 − ACTIVE
    outbound 합계"로 계산한다(2026-08-14, outbound 분리 후 수식 확정).

    재고 행과 기존 ACTIVE 예약 합계를 FOR UPDATE로 잠그고 가용재고를 확인한 뒤
    INSERT까지 한 트랜잭션 안에서 처리해, 두 사람이 동시에 같은 재고를 예약해도
    한쪽만 성공하도록 한다(직렬화 지점은 재고 행 락 — 같은 pk를 노리는 두 트랜잭션은
    이 락에서 순서가 정해지고, 뒤에 도는 쪽은 앞쪽이 커밋한 예약까지 반영된 합계로
    다시 계산되므로 중복 예약이 불가능하다).

    product: {상품명, 브랜드, 등급, ESTNO, BL, 창고, 수량, 거래처, 담당자}
    실패 시 ValueError(사유) — 호출부(API)가 400으로 변환해서 응답.
    """
    import uuid
    from datetime import datetime
    from zoneinfo import ZoneInfo

    reserve_qty = int(product.get("수량") or 0)
    if reserve_qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다")

    table = _table_for_warehouse(product["창고"])
    hr_table = "holding_records" if table == "inventory" else "azy_holding_records"

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, pk, 재고, stock_version FROM {table} WHERE 상품명=%s AND 브랜드=%s "
            f"AND 등급=%s AND ESTNO=%s AND BL=%s AND 창고=%s AND 수집일 != '' FOR UPDATE",
            (product["상품명"], product.get("브랜드", ""), product.get("등급", ""),
             product.get("ESTNO", ""), product["BL"], product["창고"]),
        )
        matches = cur.fetchall()
        if len(matches) != 1:
            raise ValueError(f"재고 매칭 {len(matches)}건 — 정확히 1건이어야 예약 가능")
        src = matches[0]
        pk  = src["pk"] or src["id"]

        cur.execute(
            f"SELECT COALESCE(SUM(수량),0) AS total FROM {hr_table} WHERE pk=%s AND status='ACTIVE' FOR UPDATE",
            (pk,),
        )
        active_sum = int(cur.fetchone()["total"] or 0)
        cur.execute(
            "SELECT COALESCE(SUM(수량),0) AS total FROM outbound WHERE pk=%s AND status='ACTIVE' FOR UPDATE",
            (pk,),
        )
        outbound_sum = int(cur.fetchone()["total"] or 0)
        available  = (src["재고"] or 0) - active_sum - outbound_sum
        if reserve_qty > available:
            raise ValueError(f"가용재고 부족(가용 {available}, 요청 {reserve_qty})")

        rec_id    = uuid.uuid4().hex
        today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d")
        cur.execute(
            f"INSERT INTO {hr_table} "
            "(id, pk, BL, ESTNO, 등급, 수량, 홀딩, 출고일, 메모, uid, 홀딩일자, status, "
            "stock_when_reserved, available_when_reserved, stock_version_when_reserved, released_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s,%s,'')",
            (rec_id, pk, product["BL"], product.get("ESTNO", ""), product.get("등급", ""), reserve_qty,
             product.get("담당자", ""), product.get("출고일", ""), product.get("거래처", ""), "reservation", today_str,
             src["재고"], available, src.get("stock_version") or 0),
        )

    return {
        "id": rec_id, "pk": pk, "table": hr_table, "수량": reserve_qty,
        "실재고_당시": src["재고"], "가용재고_당시": available,
        "stock_version_당시": src.get("stock_version") or 0,
    }


def cancel_reservation(conn, rec_id: str) -> bool:
    """예약 취소 — 물리 삭제 대신 status=CANCEL로 남겨서 이력을 보존한다
    (삭제하면 짝지어진 데이터가 안 지워져 유령으로 남는 사고를 원천 차단 — 2026-08-05).
    클라이언트가 어느 테이블 소속인지 몰라도 되도록 양쪽 다 시도한다."""
    return _set_reservation_status(conn, rec_id, "CANCEL")


def complete_reservation(conn, rec_id: str) -> bool:
    """예약 완료 처리(실제로 출고됨) — 매뉴얼/자동 완료가 이 함수 하나만 호출한다."""
    return _set_reservation_status(conn, rec_id, "COMPLETED")


def reactivate_reservation(conn, rec_id: str) -> bool:
    """COMPLETED 예약을 다시 ACTIVE로(2026-08-18, "사용완료" 되돌리기 전용).
    use_reservation이 전량 사용 분기에서 수량은 안 건드리고 status만 바꾸므로
    (아래 use_reservation 참고) 여기서도 수량 복원 없이 status만 되돌리면 된다.
    _set_reservation_status는 ACTIVE에서 출발하는 전이만 다뤄서 이 방향(반대)엔
    못 쓰고, 별도로 둔다."""
    with conn.cursor() as cur:
        for hr_table in ("holding_records", "azy_holding_records"):
            cur.execute(
                f"UPDATE {hr_table} SET status='ACTIVE', released_at='' WHERE id=%s AND status='COMPLETED'",
                (rec_id,),
            )
            if cur.rowcount:
                return True
    return False


def use_reservation(conn, rec_id: str, use_qty: int) -> bool:
    """예약 사용 완료(부분/전체) — 입력한 수량만큼 예약 수량에서 차감한다.
    남은 수량이 0이 되면 COMPLETED로 종료, 남으면 ACTIVE인 채로 수량만 줄어든다.
    실재고는 안 건드림 — 가용재고는 조회 시점에 재계산되므로 자동 반영."""
    if use_qty <= 0:
        raise ValueError("사용 수량은 1 이상이어야 합니다")
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    with conn.cursor() as cur:
        for hr_table in ("holding_records", "azy_holding_records"):
            cur.execute(
                f"SELECT 수량 FROM {hr_table} WHERE id=%s AND status='ACTIVE' FOR UPDATE",
                (rec_id,),
            )
            row = cur.fetchone()
            if not row:
                continue
            remaining = int(row["수량"] or 0)
            if use_qty > remaining:
                raise ValueError(f"예약 수량({remaining})보다 많이 사용 완료할 수 없습니다")
            if use_qty == remaining:
                cur.execute(
                    f"UPDATE {hr_table} SET status='COMPLETED', released_at=%s WHERE id=%s",
                    (now, rec_id),
                )
            else:
                cur.execute(f"UPDATE {hr_table} SET 수량=수량-%s WHERE id=%s", (use_qty, rec_id))
            return True
    return False


def update_reservation(conn, rec_id: str, updates: dict) -> bool:
    """예약 변경 — 수량/출고일/거래처를 한 번에 또는 일부만 바꿀 수 있다
    (2026-08-14, "수량변경"을 "예약변경"으로 확장). updates에 없는 필드는
    안 건드림. 거래처는 holding_records.메모 컬럼에 저장된다(get_all_active_
    reservations의 별칭과 동일).

    수량이 바뀌는 경우에만 가용재고 검사: 늘릴 땐 이 예약을 뺀 다른 ACTIVE
    예약 합계 + ACTIVE outbound 합계 기준 가용재고를 넘을 수 없다 —
    create_reservation과 같은 락 순서(재고 행 → 예약 합계)로 동시 변경/동시
    신규예약과 경합해도 안전하다.
    줄이는 건 가용재고를 늘리는 방향이라 제한이 필요 없다. 0 이하로는 못
    바꿈 — 그 경우 예약 취소(cancel)를 쓰게 한다."""
    new_qty = updates.get("수량")
    if new_qty is not None and new_qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다 (0으로 만들려면 예약 취소를 사용하세요)")

    set_cols = []
    params = []
    if new_qty is not None:
        set_cols.append("수량=%s")
        params.append(new_qty)
    if "출고일" in updates:
        set_cols.append("출고일=%s")
        params.append(updates["출고일"])
    if "거래처" in updates:
        set_cols.append("메모=%s")
        params.append(updates["거래처"])
    if "전달사항" in updates:
        set_cols.append("전달사항=%s")
        params.append(updates["전달사항"])
    if not set_cols:
        return False

    for table, hr_table in (("inventory", "holding_records"), ("azy_inventory", "azy_holding_records")):
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT pk FROM {hr_table} WHERE id=%s AND status='ACTIVE' FOR UPDATE",
                (rec_id,),
            )
            rec = cur.fetchone()
            if not rec:
                continue
            pk = rec["pk"]
            if new_qty is not None:
                cur.execute(f"SELECT 재고 FROM {table} WHERE id=%s OR pk=%s FOR UPDATE", (pk, pk))
                src = cur.fetchone()
                if not src:
                    raise ValueError("원본 재고를 찾을 수 없습니다")
                cur.execute(
                    f"SELECT COALESCE(SUM(수량),0) AS total FROM {hr_table} "
                    "WHERE pk=%s AND status='ACTIVE' AND id!=%s FOR UPDATE",
                    (pk, rec_id),
                )
                other_sum = int(cur.fetchone()["total"] or 0)
                cur.execute(
                    "SELECT COALESCE(SUM(수량),0) AS total FROM outbound WHERE pk=%s AND status='ACTIVE' FOR UPDATE",
                    (pk,),
                )
                outbound_sum = int(cur.fetchone()["total"] or 0)
                available = (src["재고"] or 0) - other_sum - outbound_sum
                if new_qty > available:
                    raise ValueError(f"가용재고 부족(가용 {available}, 요청 {new_qty})")
            cur.execute(f"UPDATE {hr_table} SET {', '.join(set_cols)} WHERE id=%s", (*params, rec_id))
            return True
    return False


def _set_reservation_status(conn, rec_id: str, status: str) -> bool:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    with conn.cursor() as cur:
        for hr_table in ("holding_records", "azy_holding_records"):
            cur.execute(
                f"UPDATE {hr_table} SET status=%s, released_at=%s WHERE id=%s AND status='ACTIVE'",
                (status, now, rec_id),
            )
            if cur.rowcount:
                return True
    return False


def try_auto_complete_by_shipment(conn, bl: str, estno: str, grade: str, shipped_qty: int) -> bool:
    """출고 기록 시트에 찍힌 실제 출고와 ACTIVE 예약을 대조해, 애매하지 않을 때만
    자동으로 완료 처리한다: 해당 BL/ESTNO/등급의 ACTIVE 예약이 정확히 1건이고,
    그 예약 수량이 출고 수량과 정확히 일치할 때만. 하나라도 안 맞으면 손대지 않고
    False 반환 — 호출부가 사람 확인 목록으로 남긴다.

    JNS/곤 창고(holding_records)만 대상 — 출고 기록 시트가 그쪽 기준으로 운영됨.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, 수량 FROM holding_records WHERE BL=%s AND ESTNO=%s AND 등급=%s AND status='ACTIVE'",
            (bl, estno, grade),
        )
        matches = cur.fetchall()
    if len(matches) != 1 or int(matches[0]["수량"] or 0) != int(shipped_qty):
        return False
    return complete_reservation(conn, matches[0]["id"])


def get_active_reservations_by_pk(conn, pk: str) -> list[dict]:
    """화면에서 "이 상품 예약 N건"을 눌렀을 때(또는 마우스오버 카드에) 상세 목록을
    보여주기 위한 조회. 어느 테이블 소속인지 몰라도 되도록 양쪽 다 찾는다."""
    result = []
    with conn.cursor() as cur:
        for hr_table in ("holding_records", "azy_holding_records"):
            cur.execute(
                f"SELECT id, 수량, 홀딩, 메모, 출고일, 홀딩일자 FROM {hr_table} WHERE pk=%s AND status='ACTIVE'",
                (pk,),
            )
            result.extend(cur.fetchall())
    return result


def get_all_active_reservations(conn) -> list[dict]:
    """전체 ACTIVE 예약 + 상품 정보(상품명/브랜드/창고 등) 조인 — "예약 현황" 탭에서
    담당자별로 묶어 보여주거나(편집자), 내 예약만 필터링(사원)할 때 씀.

    출고일/실재고/가용재고도 같이 내려줘서, 예약 이후 실재고가 줄어 예약이
    초과된 상황(2026-08-13, MAEU270161050 오버부킹 발견)을 예약 현황 화면
    에서 바로 볼 수 있게 한다. 가용재고 = 실재고 − ACTIVE 예약 합계 − ACTIVE
    outbound 합계(둘 다 자기 자신 포함, pk 기준) — /api/inventory 및
    create/update_reservation의 계산과 동일 원칙(2026-08-14)."""
    result = []
    pairs = [("holding_records", "inventory"), ("azy_holding_records", "azy_inventory")]
    with conn.cursor() as cur:
        for hr_table, inv_table in pairs:
            cur.execute(
                f"SELECT r.id, r.pk, r.수량, r.홀딩 AS 담당자, r.메모 AS 거래처, r.홀딩일자, r.출고일, "
                f"r.전달사항, "
                f"i.상품명, i.브랜드, i.등급, i.ESTNO, i.BL, i.창고, i.재고, "
                f"i.재고 - COALESCE(agg.총예약, 0) - COALESCE(ob.총출고, 0) AS 가용재고 "
                f"FROM {hr_table} r LEFT JOIN {inv_table} i ON r.pk = i.id "
                f"LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 총예약 FROM {hr_table} "
                f"           WHERE status='ACTIVE' GROUP BY pk) agg ON r.pk = agg.pk "
                f"LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 총출고 FROM outbound "
                f"           WHERE status='ACTIVE' GROUP BY pk) ob ON r.pk = ob.pk "
                f"WHERE r.status='ACTIVE' ORDER BY r.홀딩일자 DESC"
            )
            result.extend(cur.fetchall())
    return result


# ── outbound(타창고매출현황) — 예약과 완전히 분리된 별도 저장소(2026-08-14) ──
# 예약 중 출고일이 오늘인 것은 outbound로 "진짜 이동"(원본 삭제)되고, sales.html은
# 이 테이블만 보고 CRUD도 여기에만 적용한다. outbound 행의 출고일을 오늘이
# 아닌 날짜로 바꾸면 원래 창고에 맞는 예약 테이블로 다시 돌아간다. 스키마가
# holding_records/azy_holding_records와 동일해서 그대로 복사해 옮길 수 있다.
_RESERVATION_COLS = (
    "id", "pk", "BL", "ESTNO", "등급", "수량", "홀딩", "출고일", "메모", "uid",
    "홀딩일자", "status", "stock_when_reserved", "available_when_reserved",
    "stock_version_when_reserved", "released_at", "전달사항",
)


def _today_iso() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


def migrate_due_reservations_to_outbound(conn) -> int:
    """ACTIVE 예약 중 출고일이 오늘인 것을 outbound로 옮긴다(원본 삭제).
    sales.html이 목록을 불러올 때마다 먼저 호출해서 그 시점 기준 최신 상태로
    맞춘다. 옮겨진 뒤로는 실재고 가용성 계산(홀딩 합계)에서 빠진다 — 출고일이
    오늘인 예약은 이미 출고 확정 단계로 보고 예약 단계 계산에서 제외."""
    today = _today_iso()
    moved = 0
    cols = ", ".join(f"`{c}`" for c in _RESERVATION_COLS)
    placeholders = ", ".join(["%s"] * len(_RESERVATION_COLS))
    for hr_table in ("holding_records", "azy_holding_records"):
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {hr_table} WHERE status='ACTIVE' AND 출고일=%s FOR UPDATE",
                (today,),
            )
            rows = cur.fetchall()
            for row in rows:
                cur.execute(
                    f"INSERT INTO outbound ({cols}) VALUES ({placeholders})",
                    [row.get(c) for c in _RESERVATION_COLS],
                )
                cur.execute(f"DELETE FROM {hr_table} WHERE id=%s", (row["id"],))
                moved += 1
    return moved


def create_outbound(conn, product: dict) -> dict:
    """outbound(타창고매출현황) 새 항목 추가(2026-08-14). 출고일을 안 정해주면
    오늘로 기본값 지정. create_reservation()으로 예약 테이블에 우선 생성(가용
    재고 잠금 등 검증된 로직 그대로 재사용)한 뒤, migrate_due_reservations_
    to_outbound()로 출고일에 맞게 정리한다 — 출고일이 오늘이면 방금 만든 게
    바로 outbound로 넘어가고, 미래 날짜면 예약 테이블에 그대로 남는다.

    비고는 outbound 전용 컬럼(holding_records엔 없음, 2026-08-19)이라
    _RESERVATION_COLS를 거치는 create_reservation/migrate로는 못 옮기고, 여기서
    migrate 뒤에 outbound 행을 따로 한 번 더 UPDATE한다 — 출고일이 미래라 아직
    outbound로 안 넘어갔으면 이 UPDATE는 0행 적용되고 조용히 넘어간다(예약
    단계엔 비고를 붙일 자리가 없으므로 출고등록/추가 시점에 다시 넣어야 함)."""
    product = dict(product)
    if not product.get("출고일"):
        product["출고일"] = _today_iso()
    비고 = product.get("비고")
    rec = create_reservation(conn, product)
    migrate_due_reservations_to_outbound(conn)
    if 비고:
        with conn.cursor() as cur:
            cur.execute("UPDATE outbound SET 비고=%s WHERE id=%s", (비고, rec["id"]))
    return rec


def register_outbound_from_reservation(conn, rec_id: str, qty: int, 출고일: str = "", 거래처: str = "") -> dict:
    """재고장(메인) 예약현황의 "출고등록" 버튼 — 예약 수량 중 일부/전체를
    outbound로 등록한다(2026-08-14). 수량이 예약 전체와 같으면 예약 행 자체를
    outbound로 옮기고(원본 삭제), 일부만 지정하면 예약 수량만 그만큼 차감하고
    outbound에 별도 항목을 새로 만든다(use_reservation의 부분/전체 패턴과
    동일). 출고일 미지정 시 오늘로 채움, 거래처는 지정하면 덮어씀."""
    if qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다")
    if not 출고일:
        출고일 = _today_iso()

    import uuid
    for hr_table in ("holding_records", "azy_holding_records"):
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {hr_table} WHERE id=%s AND status='ACTIVE' FOR UPDATE", (rec_id,))
            row = cur.fetchone()
            if not row:
                continue
            remaining = int(row["수량"] or 0)
            if qty > remaining:
                raise ValueError(f"예약 수량({remaining})보다 많이 출고등록할 수 없습니다")

            new_id = uuid.uuid4().hex
            outbound_row = dict(row)
            outbound_row["id"] = new_id
            outbound_row["수량"] = qty
            outbound_row["출고일"] = 출고일
            if 거래처:
                outbound_row["메모"] = 거래처

            cols = ", ".join(f"`{c}`" for c in _RESERVATION_COLS)
            placeholders = ", ".join(["%s"] * len(_RESERVATION_COLS))
            cur.execute(
                f"INSERT INTO outbound ({cols}) VALUES ({placeholders})",
                [outbound_row.get(c) for c in _RESERVATION_COLS],
            )

            if qty == remaining:
                cur.execute(f"DELETE FROM {hr_table} WHERE id=%s", (rec_id,))
            else:
                cur.execute(f"UPDATE {hr_table} SET 수량=수량-%s WHERE id=%s", (qty, rec_id))
            return {"outbound_id": new_id}
    raise ValueError("예약을 찾을 수 없거나 이미 종료됨")


def get_all_outbound(conn) -> list[dict]:
    """outbound(타창고매출현황) 전체 조회 + 상품 정보(상품명/브랜드/창고/재고)
    조인. pk가 inventory/azy_inventory 어느 쪽 소속인지 outbound 자체엔 표시가
    없어서 행마다 두 테이블을 순서대로 조회한다(건수가 적어 N+1이어도 무방).
    가용재고 = 실재고 − ACTIVE 예약 합계 − ACTIVE outbound 합계(get_all_active_
    reservations와 동일 원칙, 2026-08-14). status=COMPLETED(출고완료 토글)도
    같이 내려준다 — CANCEL과 달리 화면에서 안 사라지고 회색으로 표시된다."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, pk, 수량, 홀딩 AS 담당자, 메모 AS 거래처, 홀딩일자, 출고일, status, 전달사항, 등록, 비고 "
            "FROM outbound WHERE status IN ('ACTIVE','COMPLETED') ORDER BY 홀딩일자 DESC"
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            info = None
            inv_table = None
            for t in ("inventory", "azy_inventory"):
                cur.execute(
                    f"SELECT 상품명, 브랜드, 등급, ESTNO, BL, 창고, 재고 FROM {t} WHERE id=%s",
                    (row["pk"],),
                )
                info = cur.fetchone()
                if info:
                    inv_table = t
                    break
            if info:
                hr_table = "holding_records" if inv_table == "inventory" else "azy_holding_records"
                cur.execute(
                    f"SELECT COALESCE(SUM(수량),0) AS total FROM {hr_table} WHERE pk=%s AND status='ACTIVE'",
                    (row["pk"],),
                )
                hold_sum = int(cur.fetchone()["total"] or 0)
                cur.execute(
                    "SELECT COALESCE(SUM(수량),0) AS total FROM outbound WHERE pk=%s AND status='ACTIVE'",
                    (row["pk"],),
                )
                outbound_sum = int(cur.fetchone()["total"] or 0)
                info = {**info, "가용재고": (info["재고"] or 0) - hold_sum - outbound_sum}
            result.append({**row, **(info or {})})
        return result


def _inv_table_for_pk(cur, pk: str):
    """pk가 소속된 재고 테이블 이름("inventory" 또는 "azy_inventory") 반환,
    둘 다 없으면 None."""
    for t in ("inventory", "azy_inventory"):
        cur.execute(f"SELECT id FROM {t} WHERE id=%s OR pk=%s", (pk, pk))
        if cur.fetchone():
            return t
    return None


def update_outbound(conn, rec_id: str, updates: dict) -> bool:
    """outbound 행 수정 — 수량/출고일/거래처를 부분 수정 가능. 출고일을 오늘이
    아닌 날짜로 바꾸면 원래 창고에 맞는 예약 테이블로 다시 이동(원본 삭제 후
    INSERT). 수량을 늘릴 땐 이 항목을 뺀 "같은 pk의 다른 outbound 합계 +
    ACTIVE 예약 합계" 기준 가용재고를 넘을 수 없다(둘 다 같은 재고를 두고
    경합하는 커밋이라 같이 봐야 정확함).

    수량이 바뀌면 원래 갈라져 나온 예약(register_outbound_from_reservation이
    떼어낸 그 예약 — cancel_outbound와 동일한 자연키로 매칭)과 그 차이만큼
    주고받는다(2026-08-18) — 늘리면 매칭 예약에서 그만큼 더 끌어오고, 줄이면
    그만큼 매칭 예약에 돌려준다(매칭이 없으면 cancel_outbound의 부분취소처럼
    새 예약으로 되살림). 안 그러면 매번 수정할 때마다 예약 풀과 무관하게 그냥
    더해지고 빠지는 것처럼 보여 혼란을 준다(신우냉장/CS 등 파트너 창고 출고량
    조정 시 보고된 문제). 늘리는 쪽은 매칭 예약의 남은 수량을 넘을 수 없다 —
    예약보다 많이 출고할 순 없다는 규칙이라 register_outbound_from_reservation
    과 동일하게 여기서도 막는다(2026-08-18, 예약 초과 출고 방지 요청)."""
    new_qty = updates.get("수량")
    if new_qty is not None and new_qty <= 0:
        raise ValueError("수량은 1 이상이어야 합니다")

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM outbound WHERE id=%s AND status='ACTIVE' FOR UPDATE", (rec_id,))
        row = cur.fetchone()
        if not row:
            return False
        pk = row["pk"]

        moving_back = "출고일" in updates and updates["출고일"] != _today_iso()
        qty_delta = new_qty - int(row["수량"] or 0) if new_qty is not None else 0
        match = None

        if new_qty is not None and not moving_back:
            inv_table = _inv_table_for_pk(cur, pk)
            if not inv_table:
                raise ValueError("원본 재고를 찾을 수 없습니다")
            cur.execute(f"SELECT 재고 FROM {inv_table} WHERE id=%s OR pk=%s FOR UPDATE", (pk, pk))
            stock = int((cur.fetchone() or {}).get("재고") or 0)
            hr_table = "holding_records" if inv_table == "inventory" else "azy_holding_records"
            cur.execute(
                f"SELECT COALESCE(SUM(수량),0) AS total FROM {hr_table} WHERE pk=%s AND status='ACTIVE' FOR UPDATE",
                (pk,),
            )
            hold_sum = int(cur.fetchone()["total"] or 0)
            cur.execute(
                "SELECT COALESCE(SUM(수량),0) AS total FROM outbound WHERE pk=%s AND status='ACTIVE' AND id!=%s FOR UPDATE",
                (pk, rec_id),
            )
            outbound_sum = int(cur.fetchone()["total"] or 0)
            available = stock - hold_sum - outbound_sum
            if new_qty > available:
                raise ValueError(f"가용재고 부족(가용 {available}, 요청 {new_qty})")

            if qty_delta > 0:
                cur.execute(
                    f"SELECT id, 수량 FROM {hr_table} WHERE pk=%s AND status='ACTIVE' AND 홀딩=%s "
                    "AND 메모=%s AND 홀딩일자=%s FOR UPDATE",
                    (pk, row["홀딩"], row["메모"], row["홀딩일자"]),
                )
                match = cur.fetchone()
                match_qty = int(match["수량"] or 0) if match else 0
                if qty_delta > match_qty:
                    raise ValueError(f"예약 수량({match_qty})보다 많은 수량으로 늘릴 수 없습니다")

        merged = dict(row)
        if new_qty is not None:
            merged["수량"] = new_qty
        if "출고일" in updates:
            merged["출고일"] = updates["출고일"]
        if "거래처" in updates:
            merged["메모"] = updates["거래처"]
        if "전달사항" in updates:
            merged["전달사항"] = updates["전달사항"]

        if moving_back:
            inv_table = _inv_table_for_pk(cur, pk)
            if not inv_table:
                raise ValueError("원본 재고를 찾을 수 없습니다")
            hr_table = "holding_records" if inv_table == "inventory" else "azy_holding_records"
            cols = ", ".join(f"`{c}`" for c in _RESERVATION_COLS)
            placeholders = ", ".join(["%s"] * len(_RESERVATION_COLS))
            cur.execute(
                f"INSERT INTO {hr_table} ({cols}) VALUES ({placeholders})",
                [merged.get(c) for c in _RESERVATION_COLS],
            )
            cur.execute("DELETE FROM outbound WHERE id=%s", (rec_id,))
            return True

        set_cols, params = [], []
        if new_qty is not None:
            set_cols.append("수량=%s"); params.append(new_qty)
        if "출고일" in updates:
            set_cols.append("출고일=%s"); params.append(updates["출고일"])
        if "거래처" in updates:
            set_cols.append("메모=%s"); params.append(updates["거래처"])
        if "전달사항" in updates:
            set_cols.append("전달사항=%s"); params.append(updates["전달사항"])
        if "비고" in updates:
            set_cols.append("비고=%s"); params.append(updates["비고"])
        if not set_cols:
            return False
        cur.execute(f"UPDATE outbound SET {', '.join(set_cols)} WHERE id=%s", (*params, rec_id))

        if qty_delta != 0:
            if qty_delta > 0:
                # match/한도는 위에서 이미 검증됨 — 여기선 실제로 옮기기만 함
                if match:
                    if qty_delta == int(match["수량"] or 0):
                        cur.execute(f"DELETE FROM {hr_table} WHERE id=%s", (match["id"],))
                    else:
                        cur.execute(f"UPDATE {hr_table} SET 수량=수량-%s WHERE id=%s", (qty_delta, match["id"]))
            else:
                give_back = -qty_delta
                cur.execute(
                    f"SELECT id, 수량 FROM {hr_table} WHERE pk=%s AND status='ACTIVE' AND 홀딩=%s "
                    "AND 메모=%s AND 홀딩일자=%s FOR UPDATE",
                    (pk, row["홀딩"], row["메모"], row["홀딩일자"]),
                )
                match = cur.fetchone()
                if match:
                    cur.execute(f"UPDATE {hr_table} SET 수량=수량+%s WHERE id=%s", (give_back, match["id"]))
                else:
                    revived = dict(row)
                    revived["수량"] = give_back
                    revived["출고일"] = ""
                    cols = ", ".join(f"`{c}`" for c in _RESERVATION_COLS)
                    placeholders = ", ".join(["%s"] * len(_RESERVATION_COLS))
                    cur.execute(
                        f"INSERT INTO {hr_table} ({cols}) VALUES ({placeholders})",
                        [revived.get(c) for c in _RESERVATION_COLS],
                    )
        return True


def cancel_outbound(conn, rec_id: str, delete: bool = False) -> bool:
    """outbound 취소(2026-08-14 재설계, 2026-08-18 삭제 옵션 추가) — 기본은
    예약으로 되돌린다(부분/전량 둘 다). 원래 예약이 일부만 떼어져 나온 거면
    (register_outbound_from_reservation) 남아있는 그 예약에 수량을 합치고,
    원래 예약이 통째로 옮겨진 거였거나("추가" 버튼으로 직접 만든 경우 포함)
    합칠 대상이 없으면 새 ACTIVE 예약으로 부활시킨다(update_outbound의 출고일
    변경 이동과 동일 패턴 — 물리 삭제 대신 항상 어딘가엔 살아있게 함).
    delete=True면 예약으로 되돌리지 않고 outbound 행 자체를 지운다 — 사용자가
    "출고취소" 팝업에서 아예 삭제를 선택한 경우(예약현황에 남기고 싶지 않은
    잘못 입력된 건 등).

    합칠 대상 찾기는 FK가 없어서 자연키로 한다: 같은 pk + 담당자(홀딩) +
    거래처(메모) + 홀딩일자를 가진 ACTIVE 예약 — register_outbound_from_
    reservation이 원본 행을 그대로 복사해서 만들기 때문에(거래처를 새로
    지정하지 않았다면) 이 조합이 같으면 같은 원본에서 나온 걸로 본다."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM outbound WHERE id=%s AND status='ACTIVE' FOR UPDATE", (rec_id,))
        row = cur.fetchone()
        if not row:
            return False
        if delete:
            cur.execute("DELETE FROM outbound WHERE id=%s", (rec_id,))
            return True
        pk = row["pk"]
        inv_table = _inv_table_for_pk(cur, pk)
        if not inv_table:
            raise ValueError("원본 재고를 찾을 수 없습니다")
        hr_table = "holding_records" if inv_table == "inventory" else "azy_holding_records"

        cur.execute(
            f"SELECT id FROM {hr_table} WHERE pk=%s AND status='ACTIVE' AND 홀딩=%s "
            "AND 메모=%s AND 홀딩일자=%s FOR UPDATE",
            (pk, row["홀딩"], row["메모"], row["홀딩일자"]),
        )
        match = cur.fetchone()
        if match:
            cur.execute(f"UPDATE {hr_table} SET 수량=수량+%s WHERE id=%s", (row["수량"], match["id"]))
            cur.execute("DELETE FROM outbound WHERE id=%s", (rec_id,))
            return True

        # 출고일을 그대로 두면(outbound 행은 항상 출고일=오늘) 되살린 예약이
        # 다음 /api/outbound 조회 때 migrate_due_reservations_to_outbound에
        # 바로 다시 걸려서 outbound로 튕겨 돌아간다 — 취소가 취소가 안 되는
        # 꼴이라 출고일을 비워서 예약 단계로 확실히 내려놓는다.
        revived = dict(row)
        revived["출고일"] = ""
        cols = ", ".join(f"`{c}`" for c in _RESERVATION_COLS)
        placeholders = ", ".join(["%s"] * len(_RESERVATION_COLS))
        cur.execute(
            f"INSERT INTO {hr_table} ({cols}) VALUES ({placeholders})",
            [revived.get(c) for c in _RESERVATION_COLS],
        )
        cur.execute("DELETE FROM outbound WHERE id=%s", (rec_id,))
        return True


# 등록완료 체크가 출고완료의 전제조건인 창고(2026-08-18) — 신우냉장/CS는 outbound에
# "등록" 열이 따로 생겨서, 그게 체크되기 전엔 출고완료로 못 넘어가게 막는다.
_REGISTER_REQUIRED_WAREHOUSES = {"신우냉장", "CS"}


def _pk_warehouse(cur, pk: str) -> str | None:
    for t in ("inventory", "azy_inventory"):
        cur.execute(f"SELECT 창고 FROM {t} WHERE id=%s", (pk,))
        row = cur.fetchone()
        if row:
            return row["창고"]
    return None


def toggle_outbound_complete(conn, rec_id: str) -> str:
    """타창고매출현황 "출고완료" 버튼 토글(2026-08-14) — status를 ACTIVE↔COMPLETED로
    뒤집는다. CANCEL(출고취소)과 달리 COMPLETED여도 get_all_outbound에는 계속
    나온다(화면에서 회색 배경 + 출고변경/출고취소 버튼 숨김으로만 구분).
    ACTIVE→COMPLETED로 넘어갈 때, 창고가 _REGISTER_REQUIRED_WAREHOUSES에 속하면
    등록 체크가 먼저 되어 있어야 한다(2026-08-18) — COMPLETED→ACTIVE로 되돌릴 땐
    막지 않는다. 반환값은 바뀐 뒤의 status."""
    with conn.cursor() as cur:
        cur.execute("SELECT status, pk, 등록 FROM outbound WHERE id=%s FOR UPDATE", (rec_id,))
        row = cur.fetchone()
        if not row or row["status"] not in ("ACTIVE", "COMPLETED"):
            raise ValueError("항목을 찾을 수 없거나 이미 취소됨")
        new_status = "COMPLETED" if row["status"] == "ACTIVE" else "ACTIVE"
        if new_status == "COMPLETED" and not row["등록"]:
            if _pk_warehouse(cur, row["pk"]) in _REGISTER_REQUIRED_WAREHOUSES:
                raise ValueError("등록완료 체크 후 출고완료할 수 있습니다")
        cur.execute("UPDATE outbound SET status=%s WHERE id=%s", (new_status, rec_id))
        return new_status


def toggle_outbound_register(conn, rec_id: str) -> bool:
    """타창고매출현황 "등록완료" 체크박스 토글(2026-08-18) — outbound.등록을
    뒤집는다. 반환값은 바뀐 뒤의 값."""
    with conn.cursor() as cur:
        cur.execute("SELECT 등록 FROM outbound WHERE id=%s AND status IN ('ACTIVE','COMPLETED') FOR UPDATE", (rec_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("항목을 찾을 수 없거나 이미 취소됨")
        new_value = 0 if row["등록"] else 1
        cur.execute("UPDATE outbound SET 등록=%s WHERE id=%s", (new_value, rec_id))
        return bool(new_value)


def use_outbound(conn, rec_id: str, use_qty: int) -> bool:
    """outbound 사용완료(부분/전체) — 예약의 use_reservation과 동일 패턴."""
    if use_qty <= 0:
        raise ValueError("사용 수량은 1 이상이어야 합니다")
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    with conn.cursor() as cur:
        cur.execute("SELECT 수량 FROM outbound WHERE id=%s AND status='ACTIVE' FOR UPDATE", (rec_id,))
        row = cur.fetchone()
        if not row:
            return False
        remaining = int(row["수량"] or 0)
        if use_qty > remaining:
            raise ValueError(f"수량({remaining})보다 많이 사용 완료할 수 없습니다")
        if use_qty == remaining:
            cur.execute("UPDATE outbound SET status='COMPLETED', released_at=%s WHERE id=%s", (now, rec_id))
        else:
            cur.execute("UPDATE outbound SET 수량=수량-%s WHERE id=%s", (use_qty, rec_id))
        return True


def upsert_azy_holding_record(conn, rec: dict):
    cols = ["id","pk","BL","ESTNO","등급","수량","홀딩","출고일","메모","uid","홀딩일자"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO azy_holding_records ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        cur.execute(sql, [_hr_val(c, rec) for c in cols])


def delete_azy_holding_record(conn, rec_id: str):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM azy_holding_records WHERE id=%s", (rec_id,))


def get_azy_holding_sum(conn) -> dict:
    """pk → ACTIVE 예약 수량 합계 (azy_holding_records 기준)."""
    with conn.cursor() as cur:
        cur.execute("SELECT pk, SUM(수량) as total FROM azy_holding_records WHERE pk != '' AND status='ACTIVE' GROUP BY pk")
        return {row["pk"]: int(row["total"] or 0) for row in cur.fetchall()}


# ── 변경 이력(changes_log) ───────────────────────────────────
# 사용자가 inventory/azy_inventory 행을 삽입/수정/삭제/홀딩할 때마다 한 줄씩 기록.
# 2달 지난 기록은 쌓아두지 않고 쓸 때마다 같이 정리(별도 배치 없이 자연히 롤링 삭제).
def log_change(conn, uid: str, target_table: str, target_id: str, action: str):
    # 매달 1일 자정에 pipeline/scheduler.py의 reset_changes_log 잡이 통째로 비움 —
    # 여기서는 롤링 삭제 없이 그냥 쌓기만 한다
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO changes_log (uid, target_table, target_id, action) VALUES (%s,%s,%s,%s)",
            (uid or "", target_table, target_id, action)
        )


# ── 활동 로그(activity_log, 2026-08-18) ───────────────────────
# changes_log와 별개 테이블 — changes_log는 재고장 표의 "업데이트 탭"용으로 매달
# 초기화되는 짧은 최근 활동 목록이고, activity_log는 사이트 전체 CRUD(예약/출고
# 포함)를 사용자 id 필수로 남기는 감사 로그. before/after는 JSON 스냅샷 — 어떤
# 필드가 바뀌었는지 나중에 굳이 스키마 안 건드리고 그대로 대조할 수 있게.
import json as _json

def log_activity(conn, user_id: str, action: str, table_name: str, record_id: str,
                  before: dict | None = None, after: dict | None = None,
                  summary: str = "", user_name: str = "") -> None:
    if not user_id:
        raise ValueError("activity_log는 user_id가 필수입니다")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO activity_log (user_id, user_name, action, table_name, record_id, "
            "before_json, after_json, summary) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                user_id, user_name or "", action, table_name, str(record_id),
                _json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                _json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
                summary,
            ),
        )


# ── 전략단가(price, 2026-08-19) ────────────────────────────────
# id는 이 테이블에 원래 없었는데(기존 행 0건이라 안전하게) 수정/추가 기능을
# 지원하려고 VARCHAR PRIMARY KEY로 추가함 — 나머지 테이블(inventory/outbound
# 등)과 동일한 UUID hex 컨벤션.
_PRICE_COLS = ("분류", "브랜드", "품목", "등급/포장", "EST", "창고/비고", "평중", "도매가", "전략가", "업데이트일자")

def get_all_prices(conn) -> list[dict]:
    cols = ", ".join(f"`{c}`" for c in _PRICE_COLS)
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, {cols} FROM price ORDER BY 분류, 브랜드, 품목")
        return cur.fetchall()


def create_price(conn, row: dict) -> str:
    import uuid
    new_id = uuid.uuid4().hex
    cols = ", ".join(f"`{c}`" for c in _PRICE_COLS)
    placeholders = ", ".join(["%s"] * len(_PRICE_COLS))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO price (id, {cols}) VALUES (%s, {placeholders})",
            [new_id, *[row.get(c) for c in _PRICE_COLS]],
        )
    return new_id


def update_price(conn, price_id: str, updates: dict) -> bool:
    fields = {k: v for k, v in updates.items() if k in _PRICE_COLS}
    if not fields:
        return False
    set_clause = ", ".join(f"`{k}`=%s" for k in fields)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE price SET {set_clause} WHERE id=%s", (*fields.values(), price_id))
        return cur.rowcount > 0
