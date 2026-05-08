import pandas as pd
from back_end.rename_column import rename_column
from back_end.else_df_eda import else_df_eda
from back_end.replace_name import replace_name
from back_end.jns_eda import jns_eda
from back_end.ch_plz_eda import ch_eda
from back_end.ch_plz_eda import plz_eda

def list_eda(df):
    column = [ # 19컬럼
        "사업부","수탁품","품목코드","규격단위중량","단위",
        "LOT-NO","B/L NO식별번호","ESTNO","저장구역","재고수량",
        "중량","허용수량","담보수량","적재수량","PLT수량",
        "소비기한제조일자","통관구분원산지","창고"
    ]
    
    # CS -> 한라동탄, 한라동탄 -> CS, 한라곤지암 -> 한라 로 변경
    df["창고"] = df["창고"].replace({
        "CS": "한라동탄",
        "한라동탄": "CS",
        "한라곤지암": "한라"
    })
    
    # 열 전처리 필요한 창고
    six_df = df[df["창고"].isin(["강동1", "강동2","경인","삼진1", "삼진2","대청","한라","한라동탄"])].copy()
    six_df.columns = column

    six_df = six_df[six_df["사업부"].astype(str).str.strip() != "유통사업부"]
    six_df = six_df[six_df["사업부"].astype(str).str.strip() != "제니스유통"]
    
    # 열 조정
    six_df = six_df.drop(columns=["사업부", "품목코드", "단위", "LOT-NO", "저장구역", "PLT수량", "적재수량","통관구분원산지"], errors="ignore")

    # 열 전처리 필요없는 창고
    ch = df[df["창고"] == "시에이치물류"].copy()
    jns = df[df["창고"] == "제니스(곤지암)"].copy()
    plz = df[df["창고"] == "프라자로지스"].copy()

    ch.columns = column
    jns.columns = column
    plz.columns = column

    ch = ch.drop(columns=["사업부", "규격단위중량", "단위", "ESTNO","소비기한제조일자","통관구분원산지","PLT수량", "허용수량"], errors="ignore")
    jns = jns.drop(columns=["B/L NO식별번호","품목코드","PLT수량","소비기한제조일자","PLT수량","통관구분원산지"], errors="ignore")
    plz = plz.drop(columns=["사업부", "규격단위중량", "단위", "ESTNO", "담보수량","소비기한제조일자","통관구분원산지","PLT수량", "허용수량"], errors="ignore")

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

    kd = kd.reindex(columns=columns)
    ki = ki.reindex(columns=columns)
    sjn = sjn.reindex(columns=columns)
    dch = dch.reindex(columns=columns)
    hlk = hlk.reindex(columns=columns)
    hld = hld.reindex(columns=columns)
    
    dfs = [kd, ki, sjn, dch, hlk, hld]
    dfs = [d.reindex(columns=columns) for d in dfs]

    six_warehouse = replace_name(pd.concat(dfs, ignore_index=True))
    six_warehouse = six_warehouse[six_warehouse["BL번호"].notna()]
    six_warehouse = six_warehouse.drop(columns=["허용수량", "담보수량"], errors="ignore")
    
    six_warehouse["평균중량"] = six_warehouse["평균중량"].str.replace("KG", "", regex=False)
    
    jns = jns_eda(jns)
    jns = jns[jns["수탁품"].notna()]
    # jns.to_excel("C:/Users/OWNER/.streamlit/azy_warehouse/data/jns.xlsx", index=False)

    ch = ch_eda(ch)
    plz = plz_eda(plz)

    total_data = pd.concat([six_warehouse, jns, ch, plz], ignore_index=True)
    total_data.to_excel("total_data.xlsx", index=False)

    return total_data