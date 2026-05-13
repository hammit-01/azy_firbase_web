def eda_column(df):
    columns_a = [
        "사업부","수탁품[코드]","규격단위중량","단위","LOT-NO직전화주","B/L NO식별번호",
        "ESTNO","저장구역","재고수량","중량","허용수량","담보수량","적재수량","유통기한제조일자","통관구분원산지"

    ]
    columns_b = [
        "사업부","수탁품","품목코드","규격단위중량","단위","LOT-NO직전화주 -->","B/L NO식별번호",
    	"ESTNO","저장구역","재고수량","중량","허용수량","담보수량","적재수량","PLT수량","소비기한제조일자","통관구분원산지"
    ]
    columns_c = [
        "사업부","수탁품,[코드]","규격,단위중량","단위","LOT-NO,직전화주","B/L NO,식별번호","ESTNO","저장구역",
        "재고수량","중량","허용수량","담보수량","적재수량","유통기한,제조일자","통관구분,원산지"
    ]
    columns_d = [
        "사업부","수탁품,[코드]","규격","단위","LOT-NO,직전화주","B/L NO,식별번호","ESTNO","저장구역",
        "재고수량","중량","허용수량","담보수량","적재수량","유통기한,제조일자","통관구분,원산지"
    ]
    
    drop_cols = [
        "사업부",
        "LOT-NO",
        "품목코드",
        "LOT-NO직전화주 -->",
        "PLT수량",
        "단위",
        "LOT-NO직전화주",
        "LOT-NO,직전화주",
        "저장구역",
        "허용수량",
        "담보수량",
        "적재수량",
        "통관구분원산지",
        "통관구분,원산지"
    ]

    added_df_names = [
        "베이지박스투",
        "삼일물류",
        "신우냉장",
        "오로라CS",
        "이스트밸리",
        "효성냉장",
        "희창냉장",
        "신우냉장",
        "SWC"
    ]
    
    six_df_names = [
        "강동1",
        "강동2",
        "경인",
        "삼진1",
        "삼진2",
        "대청",
        "한라",
        "한라 동탄"
    ]

    ch_jn_plz_names = [
        "시에이치물류",
        "제니스(곤지암)",
        "프라자로지스"
    ]

    df["베이지박스투"] = (df["베이지박스투"].reindex(columns=columns_a))
    df["삼일물류"] = (df["삼일물류"].reindex(columns=columns_a))
    df["신우냉장"] = (df["신우냉장"].reindex(columns=columns_a))
    df["희창냉장"] = (df["희창냉장"].reindex(columns=columns_a))

    
    df["오로라CS"] = (df["오로라CS"].reindex(columns=columns_b))
    df["효성냉장"] = (df["효성냉장"].reindex(columns=columns_b))

    df["이스트밸리"] = (df["이스트밸리"].reindex(columns=columns_c))
    
    df["SWC"] = (df["SWC"].reindex(columns=columns_d))

    for name, dfs in df.items():

        df[name] = dfs.drop(
            columns=drop_cols,
            errors="ignore"
        )

    added_df = {
        name: dfs
        for name, dfs in df.items()
        if name in added_df_names
    }

    six_df = {
        name: dfs
        for name, dfs in df.items()
        if name in six_df_names
    }

    ch_jn_plz = {
        name: dfs
        for name, dfs in df.items()
        if name in ch_jn_plz_names
    }

    return added_df, six_df, ch_jn_plz