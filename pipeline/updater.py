"""크롤 데이터 → pk 기준 dict 변환 + 홀딩 매칭 헬퍼. mysql_updater.py가 재사용한다."""
import logging
import re

import pandas as pd

log = logging.getLogger("updater")

COMPARE_FIELDS = (
    "재고", "holdingTotal",
    # 상품명·브랜드·등급·ESTNO·BL·창고·유통기한·평중·출고일은 기존 행이면 사용자 편집을
    # 보존하는 마스터 필드(mysql_updater._PRESERVE_ON_UPDATE) → 비교 대상에서 제외
    # 홀딩·상태·메모도 사용자 설정 필드 → 파이프라인 비교/덮어쓰기 대상 제외
)


def _row_sig(data: dict) -> str:
    return "|".join(str(data.get(k) or "") for k in COMPARE_FIELDS)


def _clean(s: str) -> str:
    return re.sub(r"[/\s]", "_", s.strip())


def _df_to_dict(
    df: pd.DataFrame, today: str,
    holding_sum: dict = None,
    prev_snapshot: dict = None,
    holding_rows_by_bl: dict = None,
    holding_records_by_key: dict = None,
    sheet_records: dict = None,
    employees_names: set = None,
) -> tuple:
    """Returns (result_dict, crawled_key_totals, pending_list, auto_list)."""
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
    if holding_sum            is None: holding_sum            = {}
    if prev_snapshot          is None: prev_snapshot          = {}
    if holding_rows_by_bl     is None: holding_rows_by_bl     = {}
    if holding_records_by_key is None: holding_records_by_key = {}
    if sheet_records          is None: sheet_records          = {}
    if employees_names        is None: employees_names        = set()
    result = {}
    crawled_key_totals = {}   # 홀딩 이상 감지용: 차감 전 원본 수량
    pending_list = {}          # 재고 감소: 시트 미매칭 → 수동 처리
    auto_list    = {}          # 재고 감소: 시트 매칭 → 자동 차감
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
        raw_total += qty

        # doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한
        expire_str = expire.replace("-", "") if expire else ""
        bl_last4   = _clean(bl[-4:] if len(bl) >= 4 else bl)
        est_last4  = _clean(est[-4:] if len(est) >= 4 else est) if est else ""
        doc_id     = f"{_clean(code)}_{bl_last4}_{est_last4}_{expire_str}"

        if not doc_id or doc_id.replace("_", "") == "":
            skipped_rows += 1
            skipped_qty  += qty
            log.warning(f"  pk 생성 불가 스킵: 수탁품={name[:20]} / 재고={qty}박스")
            continue

        # 홀딩 이상 감지: 차감 전 원본 수량 누적
        crawled_key_totals[doc_id] = crawled_key_totals.get(doc_id, 0) + qty

        # 홀딩 차감 + 재고 증감 감지
        h_qty         = holding_sum.get(doc_id, 0)
        effective_h_qty = h_qty  # pickle에 저장될 holdingTotal (auto 차감 시 갱신)
        prev  = prev_snapshot.get(doc_id)
        if prev is not None and "holdingTotal" in prev:
            prev_raw     = (prev.get("재고") or 0) + (prev.get("holdingTotal") or 0)
            # 현재 h_qty로 보정 — 홀딩 잡힌 이후 pickle 갱신 전 상태 보정
            prev_nonhold = max(prev_raw - h_qty, 0)
            if qty > prev_raw:
                diff    = qty - prev_raw
                net_qty = prev_nonhold + diff
                log.info(f"  [재고증가] {name[:15]} | 크롤 {prev_raw}→{qty} (+{diff}) | non-hold {prev_nonhold}→{net_qty}")
            elif qty < prev_raw:
                diff  = prev_raw - qty  # 양수: 감소량
                estno = to_str(row.get("ESTNO", "")).strip()
                grade = to_str(row.get("등급", "")).strip()

                # ① 시트에서 (BL, ESTNO, 등급) 출고 기록 확인
                sheet_entry = next(
                    (e for e in (sheet_records or {}).get(bl, [])
                     if e["estno"] == estno and e["grade"] == grade),
                    None,
                )

                is_holding_use = (
                    sheet_entry is not None
                    and sheet_entry.get("holding_checked", False)
                )

                if is_holding_use:
                    # 시트에 있으면 무조건 자동 차감 — 변경사항 탭 미표시
                    matched_rows, matched_records = _match_sheet_holding(
                        bl, estno, grade, holding_rows_by_bl, holding_records_by_key
                    )
                    all_matched = matched_records + matched_rows
                    if all_matched:
                        # holding 레코드 있음 → holding에서 차감, non-hold 유지
                        net_qty = prev_nonhold
                        # pickle holdingTotal을 차감 후 값으로 갱신 → 다음 사이클 재감지 방지
                        effective_h_qty = max(h_qty - diff, 0)
                        log.info(f"  [재고감소-자동] {name[:15]} | -{diff}박스 | hold {len(matched_rows)}행 차감")
                    else:
                        # holding 레코드 없음 → non-hold에서 직접 차감
                        net_qty = qty - h_qty
                        log.info(f"  [재고감소-자동] {name[:15]} | -{diff}박스 | non-hold 직접 차감")
                    auto_list[doc_id] = {
                        "pk":              doc_id,
                        "상품명":          name,
                        "BL":              bl,
                        "창고":            to_str(row.get("창고", "")).strip(),
                        "유통기한":        expire,
                        "diff":            diff,
                        "prev_nonhold":    prev_nonhold,
                        "matched_rows":    matched_rows,
                        "matched_records": matched_records,
                        "sheet_entry":     sheet_entry,
                    }
                else:
                    # 시트 기록 없음 → 수동 처리
                    net_qty = qty - h_qty
                    reason = "시트 기록 없음" if not sheet_entry else "수정사항 불일치"
                    pending_list[doc_id] = {
                        "pk":           doc_id,
                        "상품명":       name,
                        "BL":           bl,
                        "창고":         to_str(row.get("창고", "")).strip(),
                        "유통기한":     expire,
                        "prev_raw":     prev_raw,
                        "curr_raw":     qty,
                        "diff":         -diff,
                        "holdQty":      h_qty,
                        "prev_nonhold": prev_nonhold,
                        "curr_nonhold": max(net_qty, 0),
                        "수집일":       today,
                    }
                    log.info(f"  [재고감소-pending] {name[:15]} | 크롤 {prev_raw}→{qty} (-{diff}) | {reason}")
            else:
                net_qty = qty - h_qty
        else:
            net_qty = qty - h_qty
        if net_qty <= 0:
            skipped_rows += 1
            skipped_qty  += qty
            log.info(f"  홀딩 전량 차감 스킵: {name[:20]} / 크롤={qty} 홀딩={h_qty}")
            continue

        data = {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": name,
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO":  to_str(row.get("ESTNO", "")).strip(),
            "재고":   net_qty,
            "BL":     bl,
            "창고":   to_str(row.get("창고", "")).strip(),
            "유통기한": expire,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고일")),
            "수집일": today,
            "holdingTotal": effective_h_qty,  # auto 차감 시 차감 후 값 반영
            "_auto_상태": to_str(row.get("_auto_상태", "")).strip(),
            "_auto_메모": to_str(row.get("_auto_메모", "")).strip(),
        }
        if doc_id in result:
            # 동일 pk: 창고 코드 달라도 같은 상품 → 재고 합산
            merged_rows += 1
            merged_qty  += net_qty
            result[doc_id]["재고"] = (result[doc_id].get("재고") or 0) + net_qty
        else:
            result[doc_id] = data

    out_total = sum(v.get("재고", 0) or 0 for v in result.values())
    log.info(
        f"  [변환] 원본 {len(df)}행 {raw_total}박스 → MySQL {len(result)}건 {out_total}박스"
    )
    if skipped_rows:
        log.warning(f"  [변환] pk없음/홀딩차감 스킵: {skipped_rows}행 {skipped_qty}박스")
    if merged_rows:
        log.info(f"  [변환] pk병합: {merged_rows}행 → 재고 합산 {merged_qty}박스")

    return result, crawled_key_totals, pending_list, auto_list


def _match_sheet_holding(bl: str, estno: str, grade: str,
                          holding_rows_by_bl: dict,
                          holding_records_by_key: dict) -> tuple:
    """BL → ESTNO → 등급 순으로 holding 레코드 매칭.
    Returns (matched_all_data_rows, matched_holding_data_records) or ([], [])."""
    key = (bl, estno, grade)
    rows    = [r for r in holding_rows_by_bl.get(bl, [])
               if r["estno"] == estno and r["grade"] == grade]
    records = holding_records_by_key.get(key, [])
    return rows, records
