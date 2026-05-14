import pandas as pd
from back_end.else_df_eda import else_df_eda
from back_end.replace_name import replace_name
from back_end.jns_eda import jns_eda
from back_end.ch_plz_eda import ch_eda
from back_end.ch_plz_eda import plz_eda
from back_end.eda_column import column_split

def list_eda(warehouse_dfs, jns):
    jns_names = [
        "곤SWC",
        "곤대재",
        "곤CS",
        "곤지암",
        "곤대청",
        "곤삼진2"
    ]
    added_df, six_df, ch_plz = column_split(warehouse_dfs)

    print(six_df.keys())
    print(added_df.keys())

    ch = ch_plz["시에이치물류"].copy()
    plz = ch_plz["프라자로지스"].copy()
    
    kd = pd.concat(
        [
            six_df["강동1"],
            six_df["강동2"]
        ],
        ignore_index=True
    )
    ki = six_df["경인"].copy()
    sjn = pd.concat(
        [
            six_df["삼진1"],
            six_df["삼진2"]
        ],
        ignore_index=True
    )
    dch = six_df["대청"].copy()
    hlk = six_df["한라"].copy()
    hld = six_df["한라 동탄"].copy()

    # # 함수 적용
    # kd,ki,sjn,dch,hlk,hld = else_df_eda(six_df)


    ch.to_excel("ch.xlsx", index=False)
    jns.to_excel("jns.xlsx", index=False)
    plz.to_excel("plz.xlsx", index=False)
    kd.to_excel("kd.xlsx", index=False)
    ki.to_excel("ki.xlsx", index=False)
    sjn.to_excel("sjn.xlsx", index=False)
    
    dch.to_excel("dch.xlsx", index=False)
    hlk.to_excel("hlk.xlsx", index=False)
    hld.to_excel("hld.xlsx", index=False)

    # columns = [
    #     "수탁품","브랜드","등급","ESTNO","평균중량","BL번호",
    #     "이력번호","재고수량",
    #     "중량","허용수량",
    #     "담보수량","창고",
    #     "유통기한","제조일자"
    # ]

    # new_six_df = pd.concat(
    #     [kd, ki, sjn, dch, hlk, hld],
    #     ignore_index=True
    # )
    # new_six_df = new_six_df.reindex(columns=columns)

    # six_warehouse = replace_name(new_six_df)
    # six_warehouse = six_warehouse[six_warehouse["BL번호"].notna()]
    
    # six_warehouse["평균중량"] = six_warehouse["평균중량"].str.replace("KG", "", regex=False)
    
    # jns = jns_eda(jns)
    # jns = jns[jns["수탁품"].notna()]
    # # jns.to_excel("C:/Users/OWNER/.streamlit/azy_warehouse/data/jns.xlsx", index=False)

    # ch = ch_eda(ch)
    # plz = plz_eda(plz)

    # added_df = pd.concat(
    #     list(added_df.values()),
    #     ignore_index=True
    # )
    # total_data = pd.concat([six_warehouse, jns, ch, plz, added_df], ignore_index=True)

    # total_data = total_data.replace("*", "")
    # total_data.to_excel("total_data.xlsx", index=False)
    # added_df.to_excel("added_df.xlsx", index=False)
    
    return 0 #total_data