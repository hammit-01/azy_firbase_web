import pandas as pd
from back_end.eda_else_df import else_df_eda
from back_end.jns_eda import jns_eda
from back_end.eda_ch_plz_cs import ch_eda
from back_end.eda_ch_plz_cs import plz_eda
from back_end.eda_ch_plz_cs import cs_eda
from back_end.replace_name import replace_name
from back_end.eda_standard import eda_standard
from back_end.eda_common import eda_common
from back_end.eda_added import eda_added
from back_end.exception_safe import safe_eda
from back_end.exception_safe import safe_df
from back_end.crawling_handmade import crawling_handmade


# warehouses = [
#     "베이지박스투",
#     "삼일물류",
#     "신우냉장",
#     "오로라CS",
#     "이스트밸리",
#     "효성냉장",
#     "희창냉장",
#     "SWC",
#     "시에이치물류",
#     "프라자로지스",
#     "강동1",
#     "강동2",
#     "삼진1",
#     "삼진2",
#     "경인",
#     "대청",
#     "대재",
#     "한라",
#     "한라 동탄",
#     "CS"
# ]

def list_eda(final_df, jns):
    # 통합 행 전처리
    # final_df = eda_common(final_df)

    # warehouse_dfs = {
    #     name: group.copy()
    #     for name, group in final_df.groupby("창고")
    # }

    # for w in warehouses:
    #     if w not in warehouse_dfs:
    #         print(f"{w}: 데이터 없음")
    #         warehouse_dfs[w] = pd.DataFrame()
    
    # beige = warehouse_dfs["베이지박스투"].copy()
    # samil = warehouse_dfs["삼일물류"].copy()
    # sinu = warehouse_dfs["신우냉장"].copy()
    # aurora = warehouse_dfs["오로라CS"].copy()
    # eastbelly = warehouse_dfs["이스트밸리"].copy()
    # daejae = warehouse_dfs["대재"].copy()
    # hyosung = warehouse_dfs["효성냉장"].copy()
    # huichang = warehouse_dfs["희창냉장"].copy()
    # swc = warehouse_dfs["SWC"].copy()

    # ch = warehouse_dfs["시에이치물류"].copy()
    # plz = warehouse_dfs["프라자로지스"].copy()

    # kd = pd.concat([warehouse_dfs["강동1"],warehouse_dfs["강동2"]],ignore_index=True)
    # sjn = pd.concat([warehouse_dfs["삼진1"],warehouse_dfs["삼진2"]],ignore_index=True)
    # ki = warehouse_dfs["경인"].copy()
    # dch = warehouse_dfs["대청"].copy()
    # hlk = warehouse_dfs["한라"].copy()
    # hld = warehouse_dfs["한라 동탄"].copy()
    # cs = warehouse_dfs["CS"].copy()
    # cs.to_excel("cs.xlsx", index=False)

    # # 함수 적용
    # beige = safe_df(beige, "베이지박스투")
    # samil = safe_df(samil, "삼일물류")
    # sinu = safe_df(sinu, "신우냉장")
    # aurora = safe_df(aurora, "오로라CS")
    # eastbelly = safe_df(eastbelly, "이스트밸리")
    # hyosung = safe_df(hyosung, "효성냉장")
    # huichang = safe_df(huichang, "희창냉장")
    # swc = safe_df(swc, "SWC")
    # daejae = safe_df(daejae, "대재")
    # added_df = eda_added(beige, samil, sinu, aurora, eastbelly, hyosung, daejae, huichang, swc)

    # kd = safe_df(kd, "KD")
    # ki = safe_df(ki, "KI")
    # sjn = safe_df(sjn, "SJN")
    # dch = safe_df(dch, "DCH")
    # hlk = safe_df(hlk, "HLK")
    # hld = safe_df(hld, "HLD")
    # six_df = else_df_eda(kd, ki, sjn, dch, hlk, hld)

    # jns = safe_eda(jns_eda, jns, "JNS")
    # ch = safe_eda(ch_eda, ch, "CH")
    # plz = safe_eda(plz_eda, plz, "PLZ")
    # cs = safe_eda(cs_eda, cs, "CS")
    # hand_df = crawling_handmade()
    # total_data = pd.concat([added_df,six_df,ch,plz,jns,hand_df,cs], ignore_index=True)

    # total_data = total_data.drop(columns=["중량"],errors="ignore")
    # total_data = replace_name(total_data)
    # total_data = eda_standard(total_data)

    # total_data = total_data.drop_duplicates().copy()
    # total_data = total_data.drop_duplicates(
    #     subset=["BL번호", "재고수량"]
    # ).reset_index(drop=True)

    
    df = jns_eda(jns)
    df = df.drop(columns=["중량"],errors="ignore")
    df = replace_name(df)
    df = eda_standard(df)

    # pk 기준 집계: 같은 pk(코드+BL+유통기한)는 재고수량 합산, 나머지는 첫 번째 값 유지
    # (replace_name/eda_standard 이후 이름이 동일해진 경우에도 수량 보존)
    if "pk" in df.columns and "재고수량" in df.columns:
        before_rows = len(df)
        before_qty = int(pd.to_numeric(df["재고수량"], errors="coerce").fillna(0).sum())
        qty_sum = df.groupby("pk", sort=False)["재고수량"].sum().reset_index()
        first_rows = df.drop_duplicates(subset="pk", keep="first").drop(columns=["재고수량"])
        df = first_rows.merge(qty_sum, on="pk", how="left").reset_index(drop=True)
        after_qty = int(pd.to_numeric(df["재고수량"], errors="coerce").fillna(0).sum())
        if before_rows != len(df):
            print(f"[EDA] pk 중복 합산: {before_rows}행→{len(df)}행 | 수량 {before_qty}→{after_qty}박스")
    else:
        df = df.drop_duplicates().reset_index(drop=True)

    return final_df, df

