import logging
import pandas as pd

log = logging.getLogger("eda")
from back_end.eda_else_df import else_df_eda
from back_end.jns_eda import jns_eda
from back_end.eda_ch_plz_cs import ch_eda
from back_end.eda_ch_plz_cs import plz_eda
from back_end.eda_ch_plz_cs import cs_eda
from back_end.eda_ch_plz_cs import irn_eda
from back_end.replace_name import replace_name
from back_end.eda_standard import eda_standard
from back_end.eda_common import eda_common
from back_end.eda_added import eda_added
from back_end.exception_safe import safe_eda
from back_end.exception_safe import safe_df
from back_end.crawling_handmade import crawling_handmade


warehouses = [
    "베이지박스투",
    "삼일물류",
    "신우냉장",
    "오로라CS",
    "이스트밸리",
    "효성냉장",
    "희창냉장",
    "SWC",
    "시에이치물류",
    "프라자로지스",
    "강동1",
    "강동2",
    "삼진1",
    "삼진2",
    "경인",
    "대청",
    "대재",
    "한라곤지암",
    "한라동탄",
    "CS",
    "아이린냉장"
]

def list_eda(final_df, jns):
    final_df = eda_common(final_df)

    warehouse_dfs = {
        name: group.copy()
        for name, group in final_df.groupby("창고")
    } if not final_df.empty else {}

    for w in warehouses:
        if w not in warehouse_dfs:
            warehouse_dfs[w] = pd.DataFrame()

    beige = warehouse_dfs["베이지박스투"].copy()
    samil = warehouse_dfs["삼일물류"].copy()
    sinu = warehouse_dfs["신우냉장"].copy()
    aurora = warehouse_dfs["오로라CS"].copy()
    eastbelly = warehouse_dfs["이스트밸리"].copy()
    daejae = warehouse_dfs["대재"].copy()
    hyosung = warehouse_dfs["효성냉장"].copy()
    huichang = warehouse_dfs["희창냉장"].copy()
    swc = warehouse_dfs["SWC"].copy()

    ch = warehouse_dfs["시에이치물류"].copy()
    plz = warehouse_dfs["프라자로지스"].copy()

    kd = pd.concat([warehouse_dfs["강동1"], warehouse_dfs["강동2"]], ignore_index=True)
    sjn = pd.concat([warehouse_dfs["삼진1"], warehouse_dfs["삼진2"]], ignore_index=True)
    ki = warehouse_dfs["경인"].copy()
    dch = warehouse_dfs["대청"].copy()
    hlk = warehouse_dfs["한라곤지암"].copy()
    hld = warehouse_dfs["한라동탄"].copy()
    cs = warehouse_dfs["CS"].copy()
    irn = warehouse_dfs["아이린냉장"].copy()

    beige = safe_df(beige, "베이지박스투")
    samil = safe_df(samil, "삼일물류")
    sinu = safe_df(sinu, "신우냉장")
    aurora = safe_df(aurora, "오로라CS")
    eastbelly = safe_df(eastbelly, "이스트밸리")
    hyosung = safe_df(hyosung, "효성냉장")
    huichang = safe_df(huichang, "희창냉장")
    swc = safe_df(swc, "SWC")
    daejae = safe_df(daejae, "대재")
    added_df = eda_added(beige, samil, sinu, aurora, eastbelly, hyosung, daejae, huichang, swc)

    kd = safe_df(kd, "KD")
    ki = safe_df(ki, "KI")
    sjn = safe_df(sjn, "SJN")
    dch = safe_df(dch, "DCH")
    hlk = safe_df(hlk, "HLK")
    hld = safe_df(hld, "HLD")
    try:
        six_df = else_df_eda(kd, ki, sjn, dch, hlk, hld)
    except (ValueError, Exception) as e:
        print(f"else_df_eda 오류 (빈 데이터로 대체): {e}")
        six_df = pd.DataFrame()

    ch = safe_eda(ch_eda, ch, "CH")
    plz = safe_eda(plz_eda, plz, "PLZ")
    cs = safe_eda(cs_eda, cs, "CS")
    irn = safe_df(irn, "아이린냉장")
    irn = safe_eda(irn_eda, irn, "IRN")
    hand_df = crawling_handmade()

    # ── azy_inventory용: JNS 제외 전 창고 ──────────────────
    azy_data = pd.concat([added_df, six_df, ch, plz, cs, irn, hand_df], ignore_index=True)
    azy_data = replace_name(azy_data)
    azy_data = eda_standard(azy_data)
    azy_data = replace_name(azy_data)
    # 중량은 dedup 이후에 제거 — 같은 BL·수량·유통기한이라도 중량이 다르면
    # 별도 로트이므로 drop_duplicates()가 먼저 이걸로 구분할 수 있어야 함
    azy_data = azy_data.drop_duplicates().reset_index(drop=True)
    azy_data = azy_data.drop(columns=["중량"], errors="ignore")

    # ── inventory용: JNS만 (독립 스케줄에서도 재사용 가능하도록 분리) ──
    total_data = jns_only_eda(jns)

    return final_df, total_data, azy_data


def jns_only_eda(jns_raw):
    """JNS(제니스) 크롤링 원본 → inventory용 최종 데이터.
    list_eda()의 JNS 처리 블록을 분리 — 독립 스케줄(run_jns_pipeline)에서도 동일 로직 재사용."""
    jns = safe_eda(jns_eda, jns_raw, "JNS")
    if jns is None or jns.empty:
        # 메인(나머지 창고) 잡은 JNS를 crawl_all(exclude=...)로 아예 안 크롤링하므로
        # 여기 항상 빈 데이터로 들어옴 — 정상 상황, 조용히 빈 결과 반환
        return pd.DataFrame()

    total_data = pd.concat([jns], ignore_index=True)
    total_data = total_data.drop(columns=["중량"], errors="ignore")
    total_data = replace_name(total_data)
    total_data = eda_standard(total_data)
    total_data = replace_name(total_data)
    total_data = total_data.reset_index(drop=True)

    # pk 기준 집계 (JNS 전용)
    if "pk" in total_data.columns and "재고수량" in total_data.columns:
        total_data["재고수량"] = pd.to_numeric(
            total_data["재고수량"].astype(str).str.replace(",", "", regex=False),
            errors="coerce"
        ).fillna(0).astype(int)

        nan_pk_mask = total_data["pk"].isna()
        no_pk_data = total_data[nan_pk_mask].drop_duplicates().reset_index(drop=True)
        pk_data    = total_data[~nan_pk_mask].copy()

        if not pk_data.empty:
            before_rows = len(pk_data)
            before_qty  = int(pk_data["재고수량"].sum())
            qty_sum    = pk_data.groupby("pk", sort=False)["재고수량"].sum().reset_index()
            first_rows = pk_data.drop_duplicates(subset="pk", keep="first").drop(columns=["재고수량"])
            pk_data    = first_rows.merge(qty_sum, on="pk", how="left").reset_index(drop=True)
            after_qty  = int(pk_data["재고수량"].fillna(0).sum())
            if before_rows != len(pk_data) or before_qty != after_qty:
                log.info(f"[EDA] pk 중복 합산: {before_rows}행→{len(pk_data)}행 | {before_qty}→{after_qty}박스")

        total_data = pd.concat([pk_data, no_pk_data], ignore_index=True)
    else:
        total_data = total_data.drop_duplicates().reset_index(drop=True)

    return total_data
