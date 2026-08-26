"""이고(창고이동) 취합 시트 → moving_inventory 동기화용 리더."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("moving_reader")

SHEET_ID  = "1z7nYU9lfQT7d5boRwiU-zttwx90uVlUw2Y77Ydok6LY"  # 2026-08-03, "창고 이고"+"창고 홀딩" 통합된 "창고 취합"으로 교체
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
    "processed":    "처리",
}

_TRUTHY = (True, "TRUE", "true", "True", 1, "1")


def _tab_name(dt=None) -> str:
    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    return "이고_" + dt.strftime("%Y-%m-%d")


def load_moving_rows(dt=None) -> list[dict]:
    """dt 탭(기본 오늘)의 이고 취합 행 → [{id, 상품명, 브랜드, 등급, ESTNO, 재고,
    BL, 이동창고, 비고}, ...] 실패 시 [] 반환(파이프라인 중단 없음).

    익일 미리보기(2026-08-24): dt에 내일 날짜를 넘기면 내일 탭을 읽되, 각 행의
    id를 그 탭 날짜 기준으로 만들고(오늘 탭 id와 안 겹치게) 비고에 "익일 이고"를
    붙인다 — 호출부(scheduler.py)가 이 결과를 apply_moving_deductions()에는
    절대 넘기지 않고 sync_moving_inventory()에만 얹어서, 재고 차감 없이 재고장에
    미리보기 행으로만 보이게 한다."""
    try:
        import gspread
    except ImportError:
        log.warning("gspread 미설치 (pip install gspread) → 스킵")
        return []

    if dt is None:
        dt = datetime.now(ZoneInfo("Asia/Seoul"))
    is_today = dt.date() == datetime.now(ZoneInfo("Asia/Seoul")).date()

    tab = _tab_name(dt)
    today = dt.strftime("%Y%m%d")
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
        if row.get(_COL["processed"]) in _TRUTHY:
            # 이미 '처리' 열에 체크된(입고 완료로 확정 표시된) 행 — 매 사이클
            # 도착 재확인을 반복할 필요 없이 그냥 건너뛴다.
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
        row_note = str(row.get(_COL["note"], "") or "").strip()
        history_last4 = row_note[-4:] if ("출고분" in bl and row_note) else ""

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
            # 오늘 탭은 시트의 "수정사항" 메모를 그대로 노출(기존 동작 유지),
            # 내일 탭은 이 메모를 덮고 "익일 이고" 태그로 확정 — scheduler.py의
            # 재차감 제외 필터와 firebase.js의 미리보기 구분이 이 문자열과
            # 정확히 일치해야 동작한다(2026-08-26, row_note와 변수명이 같아서
            # 이 태그가 한 번도 실제로 안 붙던 버그 수정).
            "비고":    row_note if is_today else "익일 이고",
        })

    # 같은 이고 요청이 시트에 행만 다르게 중복 입력된 경우 방지 — apply_moving_deductions는
    # id(행 인덱스) 기준 이력이 없어 매 사이클 moving_rows를 그대로 다시 차감하므로,
    # 여기서 걸러두지 않으면 홀딩 시트에서 났던 것과 같은 중복 차감이 그대로 재현된다
    # (2026-08-05, 홀딩 시트 중복 처리 버그 수정 후 같은 패턴 점검하며 추가).
    seen: dict = {}
    deduped = []
    for row in result:
        key = (row["상품명"], row["브랜드"], row["등급"], row["ESTNO"],
               row["BL"], row["이력번호"], row["출고창고"], row["이동창고"], row["재고"])
        if key in seen:
            log.warning(f"  [이고] 중복 행 스킵: {row['상품명'][:20]} / {row['BL']} (첫 등장: {seen[key]})")
            continue
        seen[key] = row["id"]
        deduped.append(row)

    log.info(f"  [이고] '{tab}' 탭 {len(deduped)}건 로드" + (f" ({len(result)-len(deduped)}건 중복 제외)" if len(deduped) != len(result) else ""))
    return deduped
