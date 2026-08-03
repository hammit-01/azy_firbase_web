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


_INT_COLS   = {"재고", "holdingTotal", "원본재고"}
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
    상품명에 "동결"이 있으면 상태를 freeze로, 상태가 freeze면 상품명 앞에 "동결"을 붙인다."""
    name = str(row.get("상품명") or "").strip()
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
    (lambda row: row.get("상품명") == "양지OFF" and str(row.get("창고") or "").startswith("곤"), "양지ON"),
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
            "holdingTotal","holdingRecordId","이상","원본재고"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO inventory ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        data = [[_val(c, sync_grade_clear(sync_name_rename(sync_estno_prefix(sync_freeze(row))))) for c in cols] for row in rows]
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
    """pk → 수량 합계 (holding_records 기준)."""
    with conn.cursor() as cur:
        cur.execute("SELECT pk, SUM(수량) as total FROM holding_records WHERE pk != '' GROUP BY pk")
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


def get_employees(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT 이름 FROM employees")
        return {row["이름"] for row in cur.fetchall()}


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
            "holdingTotal","holdingRecordId","이상","원본재고"]
    placeholders = ", ".join(["%s"] * len(cols))
    col_names    = ", ".join([f"`{c}`" for c in cols])
    update_part  = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id"])
    sql = (f"INSERT INTO azy_inventory ({col_names}) VALUES ({placeholders}) "
           f"ON DUPLICATE KEY UPDATE {update_part}")
    with conn.cursor() as cur:
        data = [[_val(c, sync_grade_clear(sync_name_rename(sync_estno_prefix(sync_freeze(row))))) for c in cols] for row in rows]
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
    거기 계속 살아있어야 함)."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE yesterday_inventory")
        cur.execute("INSERT INTO yesterday_inventory SELECT * FROM inventory")
        cur.execute("TRUNCATE TABLE yesterday_azy_inventory")
        cur.execute("INSERT INTO yesterday_azy_inventory SELECT * FROM azy_inventory")


def sync_moving_inventory(conn, rows: list[dict]):
    """이고(창고이동) 취합 시트 → moving_inventory 통째로 교체.
    이 테이블은 '오늘' 상태만 보여주는 용도라 매 사이클 전체 삭제 후 다시 채운다."""
    cols = ["id", "상품명", "브랜드", "등급", "ESTNO", "재고", "BL", "출고창고", "이동창고"]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM moving_inventory")
        if rows:
            placeholders = ", ".join(["%s"] * len(cols))
            col_names    = ", ".join([f"`{c}`" for c in cols])
            sql = f"INSERT INTO moving_inventory ({col_names}) VALUES ({placeholders})"
            data = [[row.get(c, "") for c in cols] for row in rows]
            cur.executemany(sql, data)


_MOVING_MATCH_COLS = ("상품명", "브랜드", "등급", "ESTNO", "BL")


def _table_for_warehouse(warehouse: str) -> str:
    # JNS(제니스) 하위창고는 전부 "곤" 접두 — inventory 테이블, 그 외 타창고는 azy_inventory
    return "inventory" if str(warehouse or "").startswith("곤") else "azy_inventory"


def apply_moving_deductions(conn, moving_rows: list[dict], deduct_targets=("inventory", "azy_inventory")) -> list[dict]:
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

    반환값: 아직 미입고라 moving_inventory에 그대로 남겨야 하는 행 목록.
    """
    def _matched_qty(cur, table, row, warehouse):
        where = " AND ".join(f"{c}=%s" for c in _MOVING_MATCH_COLS) + " AND 창고=%s"
        params = tuple(row[c] for c in _MOVING_MATCH_COLS) + (warehouse,)
        cur.execute(f"SELECT COALESCE(SUM(재고), 0) AS qty FROM {table} WHERE {where}", params)
        return int(cur.fetchone()["qty"] or 0)

    _YESTERDAY_TABLE = {"inventory": "yesterday_inventory", "azy_inventory": "yesterday_azy_inventory"}

    remaining = []
    with conn.cursor() as cur:
        for row in moving_rows:
            dest_table = _table_for_warehouse(row["이동창고"])
            arrived_qty  = _matched_qty(cur, dest_table, row, row["이동창고"])
            baseline_qty = _matched_qty(cur, _YESTERDAY_TABLE[dest_table], row, row["이동창고"])
            if arrived_qty >= baseline_qty + row["재고"]:
                continue  # 어제보다 이고 수량만큼 늘었음 — 입고 완료, 더 이상 표시 안 함
            remaining.append(row)

        for row in remaining:
            src_table = _table_for_warehouse(row["출고창고"])
            if src_table not in deduct_targets:
                continue
            where = " AND ".join(f"{c}=%s" for c in _MOVING_MATCH_COLS) + " AND 창고=%s"
            params = (row["재고"],) + tuple(row[c] for c in _MOVING_MATCH_COLS) + (row["출고창고"],)
            cur.execute(
                f"UPDATE {src_table} SET 재고 = GREATEST(재고 - %s, 0) WHERE {where}",
                params,
            )

    return remaining


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
    with conn.cursor() as cur:
        cur.execute("SELECT pk, SUM(수량) as total FROM azy_holding_records WHERE pk != '' GROUP BY pk")
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
