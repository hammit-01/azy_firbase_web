"""MySQL 연결 및 공통 쿼리 유틸리티."""
import pymysql
import pymysql.cursors
from contextlib import contextmanager

_CONFIG = {
    "host":    "localhost",
    "user":    "hyemi",
    "password": "0943",
    "database": "azy_warehouse",
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

@contextmanager
def get_conn():
    conn = pymysql.connect(**_CONFIG)
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


def upsert_inventory(conn, rows: list[dict]):
    """inventory 테이블 upsert (INSERT ... ON DUPLICATE KEY UPDATE)."""
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
        data = [[_val(c, row) for c in cols] for row in rows]
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
    cols = ["id","pk","BL","ESTNO","등급","수량","홀딩","출고일","메모"]
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
        data = [[_val(c, row) for c in cols] for row in rows]
        cur.executemany(sql, data)


def delete_azy_inventory(conn, ids: list[str]):
    if not ids:
        return
    placeholders = ", ".join(["%s"] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM azy_inventory WHERE id IN ({placeholders})", ids)


def upsert_azy_holding_record(conn, rec: dict):
    cols = ["id","pk","BL","ESTNO","등급","수량","홀딩","출고일","메모"]
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


def get_azy_snapshot(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM azy_inventory WHERE 수집일 != ''")
        return {row["id"]: dict(row) for row in cur.fetchall()}
