def jns_eda(df):
    df = df.drop_duplicates()
    df = df.drop(columns=["창고", "평균중량", "수집일"], errors="ignore")
    df["저장구역"] = df["저장구역"].replace({
        "(주)SWC": "곤SWC",
        "(주)대재냉장": "곤대재",
        "CS냉장": "곤CS",
        "대청냉장(주)": "곤대청",
        "삼진2냉장": "곤삼진2"
    })
    
    df.rename(columns={"저장구역": "창고", "소비기한제조일자": "소비기한","적재수량": "제조일자", "허용수량": "평균중량"}, inplace=True)
    
    # BL / 이력번호
    s = df["B/L NO식별번호"].astype(str)
    # 길이 조건
    mask = s.str.len() > 20
    # 1. 이력번호 (뒤 12자리)
    df.loc[mask, "이력번호"] = s.str[-12:]
    # 2. BL번호 (앞부분)
    df.loc[mask, "BL번호"] = s.str[:-12]
    # 3. 20자 이하 → 전부 BL번호
    df.loc[~mask, "BL번호"] = s
    df.loc[~mask, "이력번호"] = None
    df = df.drop(columns=["B/L NO식별번호"], errors="ignore")
    
    df["ESTNO"] = df["ESTNO"].str.replace("PFTO", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace(r"\[.*?\]", "", regex=True)
    
    return df