"""이고(창고이동) 취합 시트 → moving_inventory 동기화용 리더."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("moving_reader")

SHEET_ID  = "1Tm8Qm35npwv7zgHI4EqJiMf2AQt50Pj_B_ri1qtrM1w"
CRED_PATH = "azycompany-2c80615785a2.json"

_COL = {
    "item":         "품목",
    "brand":        "브랜드",
    "grade":        "등급",
    "estno":        "EST",
    "qty":          "수량",
    "bl":           "BL",
    "warehouse":    "출고창고",
    "to_warehouse": "이고창고",
    "note":         "수정사항",
}


def _tab_name(dt=None) -> str:
    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    return dt.strftime("%Y-%m-%d")


def load_moving_rows() -> list[dict]:
    """오늘 탭의 이고 취합 행 → [{id, 상품명, 브랜드, 등급, ESTNO, 재고, BL, 이동창고}, ...]
    실패 시 [] 반환 (파이프라인 중단 없음)."""
    try:
        import gspread
    except ImportError:
        log.warning("gspread 미설치 (pip install gspread) → 스킵")
        return []

    tab = _tab_name()
    today = tab.replace("-", "")
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
        bl = str(row.get(_COL["bl"], "") or "").strip()
        # BL을 미리 알 수 없는 이고 항목("출고분")은 BL 자리에 "OO 출고분" 같은
        # 안내 문구만 있고, 대신 수정사항 열에 이력번호를 미리 적어둔다 — 도착/출발
        # 매칭을 BL 대신 이력번호(뒤 4자리, id 안에 포함돼 있음)로 대체한다
        # (2026-08-04, 사용자 설명으로 도입).
        note = str(row.get(_COL["note"], "") or "").strip()
        history_last4 = note[-4:] if ("출고분" in bl and note) else ""

        result.append({
            "id":     f"{today}_{i}",
            "상품명":  item,
            "브랜드":  str(row.get(_COL["brand"], "") or "").strip(),
            "등급":    str(row.get(_COL["grade"], "") or "").strip(),
            "ESTNO":  str(row.get(_COL["estno"], "") or "").strip(),
            "재고":    qty,
            "BL":     bl,
            "이력번호": history_last4,
            "출고창고": str(row.get(_COL["warehouse"], "") or "").strip(),
            "이동창고": str(row.get(_COL["to_warehouse"], "") or "").strip(),
        })

    log.info(f"  [이고] '{tab}' 탭 {len(result)}건 로드")
    return result
