from back_end.eda_standard import eda_standard

# 제니스 창고 eda
def jns_eda(df):
    if df is None or df.empty:
        return
    df = df.drop_duplicates()

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
    
    df["ESTNO"] = df["ESTNO"].str.replace("PFTO", "", regex=False)
    
    # 기타정보 분리
    df["기타정보"] = df["수탁품"].str.replace(r"[가-힣\s]", "", regex=True)
    df["수탁품"] = df["수탁품"].str.replace(r"\[.*?\]", "", regex=True)

    # 불필요 컬럼 제거
    df = df.drop(
        columns=["기타정보","B/L NO식별번호"],
        errors="ignore"
    )
    
    return df