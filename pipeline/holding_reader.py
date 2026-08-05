"""홀딩 취합 시트 → 자동 홀딩 처리용 리더. moving_reader.py와 같은 패턴."""
import hashlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("holding_reader")

SHEET_ID  = "1z7nYU9lfQT7d5boRwiU-zttwx90uVlUw2Y77Ydok6LY"
CRED_PATH = "azycompany-2c80615785a2.json"

_COL = {
    "customer":  "거래처",
    "item":      "품목",
    "brand":     "브랜드",
    "grade":     "등급",
    "estno":     "EST",
    "qty":       "수량",
    "bl":        "BL",
    "warehouse": "출고창고",
    "done":      "완료",
}

_TRUTHY = (True, "TRUE", "true", "True", 1, "1")


def _tab_name(dt=None) -> str:
    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    return "홀딩_" + dt.strftime("%Y-%m-%d")


def load_holding_rows() -> list[dict]:
    """오늘 탭의 홀딩 취합 행 → [{id, 상품명, 브랜드, 등급, ESTNO, 재고, BL, 창고, 거래처}, ...]
    실패 시 [] 반환 (파이프라인 중단 없음)."""
    try:
        import gspread
    except ImportError:
        log.warning("gspread 미설치 (pip install gspread) → 스킵")
        return []

    tab = _tab_name()
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    try:
        gc = gspread.service_account(filename=CRED_PATH)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(tab)
    except Exception as e:
        log.warning(f"탭 '{tab}' 열기 실패: {e} → 스킵")
        return []

    try:
        rows = ws.get_all_records(numericise_ignore=["all"])
    except Exception as e:
        log.warning(f"데이터 읽기 실패: {e}")
        return []

    result = []
    for row in rows:
        item = str(row.get(_COL["item"], "") or "").strip()
        if not item:
            continue
        if row.get(_COL["done"]) in _TRUTHY:
            # 이미 '완료' 열에 체크된(자동 홀딩 처리 확정 표시된) 행 — 건너뛴다.
            continue
        try:
            qty = int(float(str(row.get(_COL["qty"], "") or "0").replace(",", "")))
        except (ValueError, TypeError):
            qty = 0
        if qty <= 0:
            continue

        brand     = str(row.get(_COL["brand"], "") or "").strip()
        grade     = str(row.get(_COL["grade"], "") or "").strip()
        estno     = str(row.get(_COL["estno"], "") or "").strip()
        bl        = str(row.get(_COL["bl"], "") or "").strip()
        warehouse = str(row.get(_COL["warehouse"], "") or "").strip()
        customer  = str(row.get(_COL["customer"], "") or "").strip()

        # id를 "오늘날짜_행위치"로 쓰면, 시트가 하루 중 편집되어 행이 밀리거나 재사용될 때
        # 같은 id가 다른 요청을 가리키게 된다 — 예전 요청은 처리완료로 DB에 유령처럼 남고,
        # 그 자리를 차지한 새 요청은 "이미 처리된 id"로 오인돼 조용히 영원히 스킵된다
        # (2026-08-05, 실사용 중 발견 — 보보스미트트레이딩 25개 유령 홀딩 + 그 자리를 차지한
        # 곰푸드 요청이 무기한 미처리). 행 위치 대신 요청 내용 해시로 id를 만들어 행이
        # 밀려도 같은 요청은 같은 id를, 다른 요청은 다른 id를 갖도록 한다.
        content_key = "|".join([item, brand, grade, estno, bl, warehouse, customer, str(qty)])
        row_id = hashlib.md5(f"{today}_{content_key}".encode()).hexdigest()[:12]

        result.append({
            "id":     row_id,
            "상품명":  item,
            "브랜드":  brand,
            "등급":    grade,
            "ESTNO":  estno,
            "재고":    qty,
            "BL":     bl,
            "창고":   warehouse,
            "거래처":  customer,
        })

    log.info(f"  [홀딩] '{tab}' 탭 {len(result)}건 로드")
    return result
