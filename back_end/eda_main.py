import pandas as pd
from back_end.rename_column import rename_column
from back_end.else_df_eda import else_df_eda
from back_end.replace_name import replace_name
from back_end.jns_eda import jns_eda
from back_end.ch_plz_eda import ch_eda
from back_end.ch_plz_eda import plz_eda
from back_end.eda_column import eda_column

def list_eda(df):
    added_df, six_df, ch_jn_plz = eda_column(df)

    ch = ch_jn_plz[ch_jn_plz["창고"].isin(["시에이치물류"])].copy()
    jns = ch_jn_plz[ch_jn_plz["창고"].isin(["제니스(곤지암)"])].copy()
    plz = ch_jn_plz[ch_jn_plz["창고"].isin(["프라자로지스"])].copy()
    
    kd = ch_jn_plz[
        ch_jn_plz["창고"].isin(["강동1", "강동2"])
    ].copy()
    ki = ch_jn_plz[ch_jn_plz["창고"].isin(["경인"])].copy()
    sjn = ch_jn_plz[
        ch_jn_plz["창고"].isin(["삼진1", "삼진2"])
    ].copy()
    dch = ch_jn_plz[ch_jn_plz["창고"].isin(["대청"])].copy()
    hlk = ch_jn_plz[ch_jn_plz["창고"].isin(["한라"])].copy()
    hld = ch_jn_plz[ch_jn_plz["창고"].isin(["한라 동탄"])].copy()

    # 함수 적용
    ch, jns, plz = rename_column(ch, jns, plz)
    kd,ki,sjn,dch,hlk,hld = else_df_eda(six_df)

    columns = [
        "수탁품","브랜드","등급","ESTNO","평균중량","BL번호",
        "이력번호","재고수량",
        "중량","허용수량",
        "담보수량","창고",
        "유통기한","제조일자"
    ]

    new_six_df = pd.concat(
        [kd, ki, sjn, dch, hlk, hld],
        ignore_index=True
    )
    new_six_df = new_six_df.reindex(columns=columns)

    six_warehouse = replace_name(new_six_df)
    six_warehouse = six_warehouse[six_warehouse["BL번호"].notna()]
    
    six_warehouse["평균중량"] = six_warehouse["평균중량"].str.replace("KG", "", regex=False)
    
    jns = jns_eda(jns)
    jns = jns[jns["수탁품"].notna()]
    # jns.to_excel("C:/Users/OWNER/.streamlit/azy_warehouse/data/jns.xlsx", index=False)

    ch = ch_eda(ch)
    plz = plz_eda(plz)

    total_data = pd.concat([six_warehouse, jns, ch, plz, added_df], ignore_index=True)

    total_data = total_data.replace("*", "")
    total_data.to_excel("total_data.xlsx", index=False)
    added_df.to_excel("added_df.xlsx", index=False)
    
    return total_data