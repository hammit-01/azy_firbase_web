import re

def eda_common(df):
    if df.empty or "B/L NO식별번호" not in df.columns:
        return df
    # BL열 정제
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

    # 소비기한제조일자
    s = df["유통기한제조일자"].astype(str)
    # 날짜 분리
    df[["유통기한", "제조일자"]] = s.str.extract(
        r"(\d{4}\.\d{2}\.\d{2})\D*(\d{4}\.\d{2}\.\d{2})?"
    )

    # 기타정보 분리
    df["기타정보"] = df["수탁품"].str.replace(r"[가-힣\s]", "", regex=True)
    df["수탁품"] = df["수탁품"].str.replace(r"[^가-힣\s]", "", regex=True).str.strip()

    # 수탁품 전처리
    df["수탁품"] = (
        df["수탁품"]
        .astype(str)
        .str.replace(r"^\(.*?\)\s*", "", regex=True)
        .str.replace(r"^[^\w가-힣]+", "", regex=True)
        .str.strip()
    )

    eda_data(df)

    df = df.drop(columns=["유통기한제조일자","B/L NO식별번호", "제조일자", "이력번호"], errors="ignore")

    return df

def eda_data(df):
    # 수탁품 열 정제
    df["수탁품"] = df["수탁품"].str.replace("#", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("_", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("-", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("(우)", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("(돈)", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("(계)", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("우", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("계", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("♥", "")
    df["수탁품"] = df["수탁품"].str.replace("#4-", "")
    df["수탁품"] = df["수탁품"].str.replace("☆", "")
    df["기타정보"] = df["기타정보"].str.replace("#", "")

    # 중량 열 정제
    df["규격단위중량"] = df["규격단위중량"].str.replace("@@", "", regex=False)
    df["ESTNO"] = df["ESTNO"].str.replace("#", "")
    df["BL번호"] = df["BL번호"].replace("*", "")
    df["BL번호"] = df["BL번호"].str.replace("/", "", regex=False)

    return df