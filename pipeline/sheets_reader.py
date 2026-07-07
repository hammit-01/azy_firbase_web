"""오늘자 Google Sheets 출고 기록 로더."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("sheets_reader")

SHEET_ID  = "1z7nYU9lfQT7d5boRwiU-zttwx90uVlUw2Y77Ydok6LY"
CRED_PATH = "azycompany-2c80615785a2.json"

_COL = {
    "customer": "거래처",
    "product":  "품목",
    "brand":    "브랜드",
    "grade":    "등급",
    "estno":    "EST",
    "qty":      "수량",
    "bl":       "BL",
    "warehouse":"출고창고",
}


def _tab_name(dt=None) -> str:
    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    return dt.strftime("%Y-%m-%d")


def load_sheet_records() -> dict:
    """오늘 탭 출고 기록 → {BL: [{estno, grade, qty, customer, product, brand, warehouse}, ...]}

    시트에 기록된 행은 모두 홀딩 출고로 처리(holding_checked=True).
    실패 시 {} 반환 (파이프라인 중단 없음).
    """
    try:
        import gspread
    except ImportError:
        log.warning("gspread 미설치 (pip install gspread) → 전체 pending 처리")
        return {}

    tab = _tab_name()
    try:
        gc = gspread.service_account(filename=CRED_PATH)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(tab)
    except Exception as e:
        log.warning(f"시트 탭 '{tab}' 열기 실패: {e} → 전체 pending 처리")
        return {}

    try:
        rows = ws.get_all_records(numericise_ignore=["all"])
    except Exception as e:
        log.warning(f"시트 데이터 읽기 실패: {e}")
        return {}

    result: dict = {}
    for row in rows:
        bl      = str(row.get(_COL["bl"],  "") or "").strip()
        qty_raw = str(row.get(_COL["qty"], "") or "").strip()
        if not bl or not qty_raw:
            continue

        try:
            qty = int(float(qty_raw))
        except (ValueError, TypeError):
            continue
        if qty <= 0:
            continue

        result.setdefault(bl, []).append({
            "estno":           str(row.get(_COL["estno"],    "") or "").strip(),
            "grade":           str(row.get(_COL["grade"],    "") or "").strip(),
            "qty":             qty,
            "customer":        str(row.get(_COL["customer"], "") or "").strip(),
            "product":         str(row.get(_COL["product"],  "") or "").strip(),
            "brand":           str(row.get(_COL["brand"],    "") or "").strip(),
            "warehouse":       str(row.get(_COL["warehouse"],"") or "").strip(),
            "holding_checked": True,  # 시트 기록 = 무조건 홀딩 출고
        })

    total_rows = sum(len(v) for v in result.values())
    log.info(f"  [시트] '{tab}' 탭 {total_rows}건 로드 / BL {len(result)}종")
    return result
