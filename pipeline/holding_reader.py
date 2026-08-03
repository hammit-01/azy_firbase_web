"""홀딩 취합 시트 → 자동 홀딩 처리용 리더. moving_reader.py와 같은 패턴."""
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
}


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
    for i, row in enumerate(rows, start=1):
        item = str(row.get(_COL["item"], "") or "").strip()
        if not item:
            continue
        try:
            qty = int(float(str(row.get(_COL["qty"], "") or "0").replace(",", "")))
        except (ValueError, TypeError):
            qty = 0
        if qty <= 0:
            continue
        result.append({
            "id":     f"{today}_{i}",
            "상품명":  item,
            "브랜드":  str(row.get(_COL["brand"], "") or "").strip(),
            "등급":    str(row.get(_COL["grade"], "") or "").strip(),
            "ESTNO":  str(row.get(_COL["estno"], "") or "").strip(),
            "재고":    qty,
            "BL":     str(row.get(_COL["bl"], "") or "").strip(),
            "창고":   str(row.get(_COL["warehouse"], "") or "").strip(),
            "거래처":  str(row.get(_COL["customer"], "") or "").strip(),
        })

    log.info(f"  [홀딩] '{tab}' 탭 {len(result)}건 로드")
    return result
