"""크롤 데이터 → pk 기준 dict 변환. mysql_updater.py가 재사용한다.

예약(홀딩) 시스템 재설계(2026-08-05) 이후, 이 함수는 실재고만 다룬다.
가용재고 계산/자동 예약 완료는 여기서 하지 않고 API 조회 시점, 그리고
별도 자동완료 로직(mysql_db.py)에서 처리한다 — 크롤러는 재고 원본을
정직하게 반영하는 역할만 한다(재고 감소가 예약 때문인지 일반 출고인지
크롤 데이터만으로는 알 수 없고, 알려고 하지 않는다).
"""
import logging
import re

import pandas as pd

log = logging.getLogger("updater")

COMPARE_FIELDS = (
    "재고", "holdingTotal",
    # 상품명·등급·ESTNO는 mysql_updater._PRESERVE_ON_UPDATE가 "기존 값이 비어있지
    # 않으면 보존"하는 마스터 필드지만, 예전엔 비교 대상에서도 통째로 빠져있어서
    # 재고 수량이 그대로면 이 필드들이 새로 고쳐진 파싱 결과와 달라도 갱신 로직
    # 자체를 안 타서 영원히 옛날 값(빈 값 포함)에 고정되는 문제가 있었음
    # (2026-07-29, eda_standard 파싱 개선이 기존 행엔 전혀 안 먹던 사고).
    # 브랜드·BL·창고·유통기한·출고일은 안정적이라 굳이 안 넣었고, 평중은 실제로
    # 사이클마다 계산값이 조금씩 흔들려서(반올림 차이) 넣으면 매번 오검출로
    # "변경 114건" 같은 허위 갱신이 반복되는 걸 확인해서 제외.
    "상품명", "등급", "ESTNO",
    # 홀딩·상태·메모도 사용자 설정 필드 → 파이프라인 비교/덮어쓰기 대상 제외
)


def _row_sig(data: dict) -> str:
    return "|".join(str(data.get(k) or "") for k in COMPARE_FIELDS)


def _clean(s: str) -> str:
    return re.sub(r"[/\s]", "_", s.strip())


def _df_to_dict(df: pd.DataFrame, today: str, holding_sum: dict = None) -> dict:
    """크롤 원본 DataFrame → {pk: 실재고 데이터} 딕셔너리.

    holding_sum은 holdingTotal 컬럼에 참고용 스냅샷으로만 기록한다(화면 표시용) —
    재고 계산에는 안 쓴다. 실제 가용재고(=재고−ACTIVE 예약 합계)는 API가 조회
    시점에 계산한다.
    """
    def to_str(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        return str(v).strip()
    def to_int(v):
        try: return int(str(v).replace(",", ""))
        except: return 0
    def to_float(v):
        try:
            f = float(v)
            return None if pd.isna(f) else f
        except: return None
    def to_date(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        try: return pd.Timestamp(v).strftime("%Y.%m.%d")
        except: return str(v)

    if holding_sum is None: holding_sum = {}
    result = {}
    skipped_rows, skipped_qty = 0, 0
    merged_rows,  merged_qty  = 0, 0
    raw_total = 0

    for _, row in df.iterrows():
        code   = to_str(row.get("코드", "")).strip()
        bl     = to_str(row.get("BL번호", "")).strip()
        est    = to_str(row.get("식별번호", "")).strip()
        name   = to_str(row.get("수탁품", "")).strip()
        expire = to_date(row.get("유통기한"))
        qty    = to_int(row.get("재고수량"))
        warehouse = to_str(row.get("창고", "")).strip()
        raw_total += qty

        # doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한_창고 — 창고도 키에 포함해
        # 같은 상품이라도 창고가 다르면 별도 행으로 유지한다.
        expire_str = expire.replace("-", "") if expire else ""
        bl_last4   = _clean(bl[-4:] if len(bl) >= 4 else bl)
        est_last4  = _clean(est[-4:] if len(est) >= 4 else est) if est else ""
        doc_id     = f"{_clean(code)}_{bl_last4}_{est_last4}_{expire_str}_{_clean(warehouse)}"

        if not doc_id or doc_id.replace("_", "") == "":
            skipped_rows += 1
            skipped_qty  += qty
            log.warning(f"  pk 생성 불가 스킵: 수탁품={name[:20]} / 재고={qty}박스")
            continue

        if qty <= 0:
            skipped_rows += 1
            skipped_qty  += qty
            continue

        data = {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": name,
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO":  to_str(row.get("ESTNO", "")).strip(),
            "재고":   qty,            # 실재고 그대로 — 예약과 무관
            "원본재고": qty,          # 실재고와 동일(예약 분리 이후 별도 의미 없음, 호환용 유지)
            "BL":     bl,
            "창고":   warehouse,
            "유통기한": expire,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고일")),
            "수집일": today,
            "holdingTotal": holding_sum.get(doc_id, 0),  # 참고용 스냅샷(계산엔 미사용)
            "_auto_상태": to_str(row.get("_auto_상태", "")).strip(),
            "_auto_메모": to_str(row.get("_auto_메모", "")).strip(),
        }
        if doc_id in result:
            # 완전히 동일한 pk(창고까지 같음) — 크롤 원본에 같은 행이 중복으로 잡힌 경우, 재고 합산
            merged_rows += 1
            merged_qty  += qty
            result[doc_id]["재고"] = (result[doc_id].get("재고") or 0) + qty
            result[doc_id]["원본재고"] = result[doc_id]["재고"]
        else:
            result[doc_id] = data

    out_total = sum(v.get("재고", 0) or 0 for v in result.values())
    log.info(
        f"  [변환] 원본 {len(df)}행 {raw_total}박스 → MySQL {len(result)}건 {out_total}박스"
    )
    if skipped_rows:
        log.warning(f"  [변환] pk없음/재고0 스킵: {skipped_rows}행 {skipped_qty}박스")
    if merged_rows:
        log.info(f"  [변환] pk병합: {merged_rows}행 → 재고 합산 {merged_qty}박스")

    return result
