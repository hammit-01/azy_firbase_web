"""입고 알림(2026-11-27).

직원이 "어느 창고에 어떤 상품(브랜드/등급/상품명)이 들어오면 알려줘" 규칙을 만들면,
파이프라인이 매분 재고를 보고 새 로트가 생기거나 수량이 늘어난 행을 찾아 받을
직원들에게 알림을 쌓는다. 화면은 로그인 팝오버의 종 버튼 배지로 보여준다.

감지 방식: 규칙마다 "지난번에 본 수량"(notify_seen)을 행 단위로 기억해 두고,
  - 처음 보는 행이고 재고 > 0       → 입고(새 로트)
  - 본 적 있는 행이고 재고가 늘어남  → 입고(수량 증가)
  - 사라진 행은 기억에서 지움        → 나중에 다시 생기면 새 로트로 잡힘
규칙을 만든 순간의 재고는 기준선으로만 저장(알림 없음).
"""
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

_TABLES_READY = False


def ensure_tables(conn) -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS notify_rules ("
            " id VARCHAR(32) PRIMARY KEY, 창고 TEXT, 상품명 VARCHAR(100) DEFAULT '',"
            " 브랜드 VARCHAR(100) DEFAULT '', 등급 VARCHAR(50) DEFAULT '', ESTNO VARCHAR(50) DEFAULT '', 대상 TEXT,"
            " 생성자 VARCHAR(50), created_at DATETIME, active TINYINT DEFAULT 1)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS notify_seen ("
            " rule_id VARCHAR(32), item_key VARCHAR(255), qty INT,"
            " PRIMARY KEY (rule_id, item_key))"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS notifications ("
            " id BIGINT AUTO_INCREMENT PRIMARY KEY, rule_id VARCHAR(32), 받는사람 VARCHAR(50),"
            " message VARCHAR(500), 창고 VARCHAR(50), 상품명 VARCHAR(100), 증가 INT, 현재 INT,"
            " created_at DATETIME, read_at DATETIME NULL, INDEX idx_recv (받는사람, read_at))"
        )
        # 나중에 추가한 칸(2026-11-27) — 먼저 만들어진 테이블에 없으면 추가.
        # notifications의 브랜드/등급/ESTNO는 받은 알림을 칸별로 보여주기 위함.
        for table, col, ddl in (
            ("notify_rules", "ESTNO", "VARCHAR(50) DEFAULT '' AFTER 등급"),
            ("notifications", "브랜드", "VARCHAR(100) DEFAULT '' AFTER 창고"),
            ("notifications", "등급", "VARCHAR(50) DEFAULT '' AFTER 브랜드"),
            ("notifications", "ESTNO", "VARCHAR(50) DEFAULT '' AFTER 상품명"),
            ("notifications", "item_key", "VARCHAR(255) DEFAULT '' AFTER rule_id"),  # 알림 클릭 → 재고장 행 바로 선택
        ):
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (col,))
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    _TABLES_READY = True


def _now():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")


def _norm(v) -> str:
    return str(v or "").replace("​", "").strip().upper()


def matches(rule: dict, item: dict) -> bool:
    """프론트(js/notify.js)와 같은 규칙: 창고는 목록 중 하나, 상품명은 포함,
    브랜드·등급·ESTNO는 정확히 일치(대소문자 무시). 빈 조건은 전체."""
    if rule["창고"] and item.get("창고") not in rule["창고"]:
        return False
    if rule.get("상품명") and _norm(rule["상품명"]) not in _norm(item.get("상품명")):
        return False
    if rule.get("브랜드") and _norm(item.get("브랜드")) != _norm(rule["브랜드"]):
        return False
    if rule.get("등급") and _norm(item.get("등급")) != _norm(rule["등급"]):
        return False
    if rule.get("ESTNO") and _norm(item.get("ESTNO")) != _norm(rule["ESTNO"]):
        return False
    return True


def diff_arrivals(seen: dict, current: dict) -> list:
    """seen: {item_key: 지난번 수량}, current: {item_key: 지금 수량}
    → [(item_key, 증가량)] — 새 로트(재고>0) 또는 수량 증가."""
    out = []
    for key, qty in current.items():
        prev = seen.get(key)
        inc = qty if prev is None else qty - prev
        if inc > 0:
            out.append((key, inc))
    return out


def _load_rules(conn, active_only=True) -> list:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM notify_rules" + (" WHERE active=1" if active_only else ""))
        rows = cur.fetchall()
    for r in rows:
        r["창고"] = json.loads(r["창고"] or "[]")
        r["대상"] = json.loads(r["대상"] or "[]")
    return rows


def _load_items(conn) -> dict:
    items = {}
    with conn.cursor() as cur:
        for t in ("inventory", "azy_inventory"):
            cur.execute(f"SELECT id, 창고, 상품명, 브랜드, 등급, ESTNO, 재고 FROM {t}")
            for r in cur.fetchall():
                items[f"{t}:{r['id']}"] = r
    return items


def _current_for(rule, items) -> dict:
    return {k: int(r["재고"] or 0) for k, r in items.items() if matches(rule, r)}


def _replace_seen(cur, rule_id, current: dict):
    cur.execute("DELETE FROM notify_seen WHERE rule_id=%s", (rule_id,))
    if current:
        cur.executemany(
            "INSERT INTO notify_seen (rule_id, item_key, qty) VALUES (%s,%s,%s)",
            [(rule_id, k, q) for k, q in current.items()],
        )


# ── API용 ─────────────────────────────────────────────────────

def create_rule(conn, body: dict) -> dict:
    ensure_tables(conn)
    rule = {
        "id": uuid.uuid4().hex,
        "창고": [w for w in body.get("창고") or [] if w],
        "상품명": (body.get("상품명") or "").strip(),
        "브랜드": (body.get("브랜드") or "").strip(),
        "등급": (body.get("등급") or "").strip().upper(),
        "ESTNO": (body.get("ESTNO") or "").strip(),
        "대상": [n for n in body.get("대상") or [] if n],
        "생성자": body.get("생성자") or "",
    }
    if not rule["창고"] and not (rule["상품명"] or rule["브랜드"] or rule["등급"] or rule["ESTNO"]):
        raise ValueError("창고나 상품 조건을 하나 이상 정하세요")
    if not rule["대상"]:
        raise ValueError("받을 직원을 한 명 이상 고르세요")
    with conn.cursor() as cur:
        # 받는 사람은 만든 사람과 같은 부서(팀)만(2026-11-27). 부서가 없으면 본인만.
        cur.execute("SELECT 부서 FROM employees WHERE 이름=%s LIMIT 1", (rule["생성자"],))
        row = cur.fetchone()
        dept = (row or {}).get("부서")
        allowed = {rule["생성자"]}
        if dept:
            cur.execute("SELECT 이름 FROM employees WHERE 부서=%s", (dept,))
            allowed |= {r["이름"] for r in cur.fetchall()}
        outside = [n for n in rule["대상"] if n not in allowed]
        if outside:
            raise ValueError(f"같은 팀원만 받는 사람으로 지정할 수 있습니다: {', '.join(outside)}")
        cur.execute(
            "INSERT INTO notify_rules (id, 창고, 상품명, 브랜드, 등급, ESTNO, 대상, 생성자, created_at, active) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
            (rule["id"], json.dumps(rule["창고"], ensure_ascii=False), rule["상품명"], rule["브랜드"],
             rule["등급"], rule["ESTNO"], json.dumps(rule["대상"], ensure_ascii=False), rule["생성자"], _now()),
        )
        # 지금 있는 재고는 기준선 — 만든 직후 알림이 쏟아지지 않게
        _replace_seen(cur, rule["id"], _current_for(rule, _load_items(conn)))
    return rule


def list_rules(conn, user: str) -> list:
    """내가 만들었거나 내가 받는 규칙."""
    ensure_tables(conn)
    return [r for r in _load_rules(conn) if r["생성자"] == user or user in r["대상"]]


def delete_rule(conn, rule_id: str) -> None:
    ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM notify_rules WHERE id=%s", (rule_id,))
        cur.execute("DELETE FROM notify_seen WHERE rule_id=%s", (rule_id,))


def list_inbox(conn, user: str, limit: int = 100) -> dict:
    ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, item_key, message, 창고, 브랜드, 등급, 상품명, ESTNO, 증가, 현재, created_at, read_at FROM notifications "
            "WHERE 받는사람=%s ORDER BY id DESC LIMIT %s",
            (user, limit),
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS n FROM notifications WHERE 받는사람=%s AND read_at IS NULL", (user,))
        unread = int(cur.fetchone()["n"])
    return {"unread": unread, "data": rows}


def mark_read(conn, user: str) -> None:
    """받은 알림 모두 읽음."""
    ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE notifications SET read_at=%s WHERE 받는사람=%s AND read_at IS NULL", (_now(), user))


def set_read(conn, user: str, notif_id: int, read: bool) -> None:
    """알림 하나 읽음/안읽음 전환 — 본인 알림만."""
    ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE notifications SET read_at=%s WHERE id=%s AND 받는사람=%s",
            (_now() if read else None, notif_id, user),
        )


def delete_notification(conn, user: str, notif_id: int) -> None:
    """받은 알림 하나 삭제 — 본인 알림만."""
    ensure_tables(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM notifications WHERE id=%s AND 받는사람=%s", (notif_id, user))


# ── 파이프라인용 ──────────────────────────────────────────────

def check_rules(conn) -> int:
    """활성 규칙 전부 검사 → 입고분을 받을 직원별로 notifications에 쌓는다. 쌓은 건수 반환."""
    ensure_tables(conn)
    rules = _load_rules(conn)
    if not rules:
        return 0
    items = _load_items(conn)
    now = _now()
    created = 0
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute("SELECT item_key, qty FROM notify_seen WHERE rule_id=%s", (rule["id"],))
            seen = {r["item_key"]: int(r["qty"] or 0) for r in cur.fetchall()}
            current = _current_for(rule, items)
            for key, inc in diff_arrivals(seen, current):
                it = items[key]
                label = " ".join(x for x in (it.get("브랜드"), it.get("등급"), it.get("상품명")) if x)
                if it.get("ESTNO"):
                    label += f" (EST {it['ESTNO']})"
                msg = f"[{it.get('창고')}] {label} +{inc}박스 입고 (현재 {current[key]}박스)"
                for person in rule["대상"]:
                    cur.execute(
                        "INSERT INTO notifications (rule_id, item_key, 받는사람, message, 창고, 브랜드, 등급, 상품명, ESTNO, 증가, 현재, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (rule["id"], key, person, msg, it.get("창고"), it.get("브랜드") or "", it.get("등급") or "",
                         it.get("상품명"), it.get("ESTNO") or "", inc, current[key], now),
                    )
                    created += 1
            if current != seen:
                _replace_seen(cur, rule["id"], current)
    return created


if __name__ == "__main__":
    rule = {"창고": ["곤지암", "CS", "SWC"], "상품명": "냉장알목심", "브랜드": "excel", "등급": "pr"}
    assert matches(rule, {"창고": "곤지암", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "PR"})
    assert not matches(rule, {"창고": "곤지암", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "CAB"})
    assert not matches(rule, {"창고": "대재", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "PR"})
    # ESTNO 지정 시 일치해야, 비우면 구별 없음
    assert matches({**rule, "ESTNO": "86r"}, {"창고": "CS", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "PR", "ESTNO": "86R"})
    assert not matches({**rule, "ESTNO": "86R"}, {"창고": "CS", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "PR", "ESTNO": "245L"})
    assert matches(rule, {"창고": "CS", "상품명": "냉장알목심", "브랜드": "EXCEL", "등급": "PR", "ESTNO": "245L"})
    # 새 로트(재고>0), 수량 증가, 감소·동일·새 로트 0박스는 알림 없음
    assert diff_arrivals({"a": 10, "b": 5, "c": 3}, {"a": 15, "b": 5, "c": 1, "d": 7, "e": 0}) == [("a", 5), ("d", 7)]
    print("notify self-check OK")
