"""오늘자 Google Sheets 출고 기록 로더."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("sheets_reader")

SHEET_ID  = "1OcEoXllrRfrxSqfJTzQWB_WPLzp3xfUKMXgwhYemRyU"
CRED_PATH = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
WEEKDAYS  = ["월", "화", "수", "목", "금", "토", "일"]

# 시트 컬럼명 → 내부 키 매핑
_COL = {
    "bl":       "BL/매입처",
    "estno":    "EST",
    "grade":    "등급",
    "qty":      "수량",
    "manager":  "담당자",
    "customer": "매출처",
    "remark":   "수정사항",
    "note":     "비고",
    "cancel":   "취소",
}


def _tab_name(dt=None) -> str:
    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    return f"{dt.month}월{dt.day}일-{WEEKDAYS[dt.weekday()]}"


def load_sheet_records() -> dict:
    """오늘 탭 출고 기록 → {BL: [{estno, grade, qty, manager, customer, note}, ...]}

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
    skipped = 0
    for row in rows:
        # 체크박스 TRUE인 행만 스킵 ("FALSE" / 빈값은 정상 처리)
        cancel_val = str(row.get(_COL["cancel"], "") or "").strip().upper()
        if cancel_val in ("TRUE", "1", "Y", "예", "취소"):
            skipped += 1
            continue

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
            "estno":    str(row.get(_COL["estno"],    "") or "").strip(),
            "grade":    str(row.get(_COL["grade"],    "") or "").strip(),
            "qty":      qty,
            "manager":  str(row.get(_COL["manager"],  "") or "").strip(),
            "customer": str(row.get(_COL["customer"], "") or "").strip(),
            "remark":   str(row.get(_COL["remark"],   "") or "").strip(),
            "note":     str(row.get(_COL["note"],     "") or "").strip(),
        })

    total_rows = sum(len(v) for v in result.values())
    log.info(f"  [시트] '{tab}' 탭 {total_rows}건 로드 / BL {len(result)}종 / 취소 {skipped}건 제외")
    return result
