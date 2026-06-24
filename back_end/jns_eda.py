from back_end.eda_standard import eda_standard

# 제니스 창고 eda
def jns_eda(dfs):
    df = dfs.drop_duplicates()

    # BL / 이력번호
    s = df["B/L NO식별번호"].astype(str)
    mask = s.str.len() > 20
    df.loc[mask,  "이력번호"] = s.str[-12:]
    df.loc[mask,  "BL번호"]   = s.str[:-12]
    df.loc[~mask, "BL번호"]   = s
    df.loc[~mask, "이력번호"] = None

    df["ESTNO"] = df["ESTNO"].str.replace("PFTO", "", regex=False)

    # 기타정보 분리
    df["기타정보"] = df["수탁품"].str.replace(r"[가-힣\s]", "", regex=True)
    df["수탁품"] = df["수탁품"].str.replace(r"\[.*?\]", "", regex=True)
    df["BL번호"] = df["BL번호"].astype(str).str.replace("*",  "", regex=False)
    df["BL번호"] = df["BL번호"].astype(str).str.replace("\\", "", regex=False)

    # PK 생성: 코드_BL번호_유통기한(YYYYMMDD)_창고_재고수량
    if all(c in df.columns for c in ["코드", "BL번호", "유통기한", "창고", "재고수량"]):
        expire_str = df["유통기한"].astype(str).str.replace("-", "", regex=False)
        df["pk"] = (
            df["코드"].astype(str).str.strip() + "_" +
            df["BL번호"].astype(str).str.strip() + "_" +
            expire_str + "_" +
            df["창고"].astype(str).str.strip() + "_" +
            df["재고수량"].astype(str).str.strip()
        )

    # 불필요 컬럼 제거
    df = df.drop(
        columns=["기타정보", "B/L NO식별번호", "제조일자", "이력번호", "LOT-NO"],
        errors="ignore"
    )

    return df