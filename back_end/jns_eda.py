from back_end.eda_standard import eda_standard

# 제니스 창고 eda
def jns_eda(dfs):
    df = dfs.copy()

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

    # 이력번호 → 식별번호로 보존 (pk 생성 및 Firestore 저장용)
    if "이력번호" in df.columns:
        df["식별번호"] = df["이력번호"].fillna("").astype(str).str.strip()

    # PK 생성: 코드_BL뒤4자리_식별번호뒤4자리_유통기한
    if all(c in df.columns for c in ["코드", "BL번호", "유통기한"]):
        expire_str = df["유통기한"].fillna("미상").astype(str).str.replace("-", "", regex=False)
        bl_s       = df["BL번호"].astype(str).str.strip()
        bl_last4   = bl_s.str[-4:].str.replace("/", "_", regex=False).str.replace(" ", "_", regex=False)
        code_clean = df["코드"].astype(str).str.strip().str.replace("/", "_", regex=False).str.replace(" ", "_", regex=False)
        id_s       = df["식별번호"].astype(str).str.strip() if "식별번호" in df.columns else ""
        id_last4   = id_s.str[-4:].where(id_s != "", "").str.replace("/", "_", regex=False).str.replace(" ", "_", regex=False)
        df["pk"]   = code_clean + "_" + bl_last4 + "_" + id_last4 + "_" + expire_str

    # 불필요 컬럼 제거
    df = df.drop(
        columns=["기타정보", "B/L NO식별번호", "제조일자", "이력번호", "LOT-NO"],
        errors="ignore"
    )

    return df