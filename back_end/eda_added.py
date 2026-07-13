import pandas as pd
import re

def huichang(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    # 문자 = 브랜드
    df["브랜드"] = df["규격단위중량"].str.extract(r"([A-Za-z\s]+)")

    # 평균중량
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"(\d+(?:\.\d+)?)")[0]
        .astype(float)
    )

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def hyosung(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    # 평균중량
    s = (
        df["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    df["평균중량"] = (
        s.str.extract(r"^(.*?)(?=[A-Z])")[0]
        .astype(float)
    )
    
    df[["등급", "ESTNO", "브랜드"]] = (
        df["기타정보"]
        .str.extract(r"([A-Z]+)([A-Z0-9]+)\((.*?)\)")
    )

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def eastbelly(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    # 평균중량
    s = (
        df["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    df["평균중량"] = (
        s.str.extract(r"^(.*?)(?=[A-Z])")[0]
        .astype(float)
    )

    df["기타정보"] = df["기타정보"].str.replace(r"\[.*?\]", "", regex=True)
    
    df["등급"] = df["기타정보"].str.extract(r"([A-Z]+)")

    df["브랜드"] = ""

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def aurora(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    # 앞 숫자 = ESTNO
    df["ESTNO"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"^([A-Z0-9]+)")[0]
    )

    # 평균중량
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"(\d+(?:\.\d+)?)KG")[0]
        .astype(float)
    )
    # 브랜드 추출
    df["브랜드"] = (
        df["기타정보"]
        .str.extract(r"\.?([A-Z]+)")
    )

    # 등급 추출 (GF 같은 마지막 코드)
    df["등급"] = (
        df["기타정보"]
        .str.extract(r"\.([A-Z]+)$")[0]
        .str.lower()
    )

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def daejae(data):
    if data is None or data.empty:
        return pd.DataFrame()

    df = data.drop_duplicates().copy()

    df["평균중량"] = pd.to_numeric(
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"(\d+(?:\.\d+)?)\s*KG")[0],
        errors="coerce"
    )
    
    s = (
        df["기타정보"]
        .astype(str)
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.strip()
    )

    # =========================
    # 등급
    # =========================
    df["등급"] = s.str.extract(
        r"^(SE|CH|PS)"
    )[0]

    # =========================
    # 브랜드
    # =========================
    df["브랜드"] = s.str.extract(
        r"(SHOWCASE\(5STAR\)|EXCEL|SADIA|INCARLOPSA|PERDIGAO|PPCS|SWIFT)"
    )[0]

    # =========================
    # ESTNO
    # =========================
    df["ESTNO"] = s.str.extract(
        r"(SIF\d+|86[A-Z]|969G?|562M|ME\d+|10\.\d+/\w+)"
    )[0]



    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def sinu(data):
    if data is None or data.empty:
        return pd.DataFrame()

    # =================================================
    # 중복 제거
    # =================================================
    df = data.drop_duplicates().copy()

    # 평균중량
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"\)([\d.]+)KG")[0]
        .astype(float)
    )

    # =================================================
    # 기타정보 정리
    # EXCEL0670086M[001152] -> EXCEL0670086M
    # ()SWIFT66600969G[000000] -> SWIFT66600969G
    # =================================================
    df["기타정보"] = (
        df["기타정보"]
        .astype(str)
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.strip()
    )

    # =================================================
    # 브랜드
    # EXCEL0670086M -> EXCEL
    # SADIA5568SIF104 -> SADIA
    # =================================================
    df["브랜드"] = (
        df["기타정보"]
        .str.extract(r"^([A-Z]+)")[0]
        .str.strip()
    )

    # =================================================
    # ESTNO
    # 알려진 코드만 하드코딩한 화이트리스트라 새 코드(SIF4202 등)가 나올 때마다
    # 안 잡히거나, "02" 같은 짧은 항목이 부분 일치로 잘못 덮어쓰는 문제가 있었음
    # (예: SIF4202 → "02"도 부분 일치해서 ESTNO가 "02"로 오염됨).
    # SIF 계열은 계속 새 코드가 추가되는 패턴이라 일반 규칙(끝에 SIF+숫자)으로 먼저 처리하고,
    # 나머지 짧은 코드만 화이트리스트로 보완 — 이미 SIF로 채워진 행은 덮어쓰지 않음.
    # =================================================
    df["ESTNO"] = (
        df["기타정보"]
        .astype(str)
        .str.extract(r"(SIF\d+)$")[0]
    )

    estno_list = [
        "969G",
        "86M",
        "86E",
        "270A",
        "413",
        "02",
        "3W",
    ]

    mask_no_est = df["ESTNO"].isna()
    for est in estno_list:

        mask = (
            mask_no_est
            & df["기타정보"].astype(str).str.contains(est, na=False)
        )

        df.loc[mask, "ESTNO"] = est

    # =================================================
    # 빈 문자열 처리
    # =================================================
    df["브랜드"] = df["브랜드"].replace("", pd.NA)
    df["ESTNO"] = df["ESTNO"].replace("", pd.NA)

    # =================================================
    # 불필요 컬럼 제거
    # =================================================
    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )

    return df

def samil(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    # ESTNO
    df["ESTNO"] = df["규격단위중량"].str.extract(r"\((.*?)\)")

    # 평균중량
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )
    df["평균중량"] = (
        df["평균중량"]
        .astype(str)
        .str.replace("KG", "", regex=True).astype(float)
    )

    df["기타정보"] = df["기타정보"].str.replace(r"\[.*?\]", "", regex=True)

    # 브랜드 = () 안 문자
    df["브랜드"] = df["기타정보"].str.extract(r"\((.*?)\)")

    # 등급 = () 제외한 나머지
    df["등급"] = (
        df["기타정보"]
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.strip("/")
        .replace("", pd.NA)
    )

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def beige(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()
    
    # 평균중량
    s = (
        df["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    df["평균중량"] = (
        s.str.extract(r"^(.*?)(?=[A-Z])")[0]
        .astype(float)
    )

    # 브랜드 = () 안 문자
    df["브랜드"] = df["기타정보"].str.extract(r"\((.*?)\)")

    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )
    return df

def swc(data):
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.drop_duplicates().copy()

    # =========================
    # 평균중량
    # =========================
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.extract(r"^(.*?)(?=[A-Z])")[0]
    )

    df["평균중량"] = pd.to_numeric(
        df["평균중량"],
        errors="coerce"
    )

    # =========================
    # 기타정보 전처리
    # =========================
    s = (
        df["기타정보"]
        .astype(str)
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.replace(r"\(.*?\)", "", regex=True)
        .str.replace(r"[☆★♥]", "", regex=True)
        .str.strip()
    )

    # =========================
    # 브랜드
    # =========================
    df["브랜드"] = s.str.extract(
        r"(EXCEL|SWIFT|SADIA|IBP|TEYS|AMH|KILCOY|SHOWCASE|ACC|TONNIES)"
    )[0]

    # =========================
    # 등급
    # =========================
    df["등급"] = s.str.extract(
        r"(ANGUS_CH|SEL|PRI|PRE|CH|GF|SE|UN)"
    )[0]

    # =========================
    # ESTNO
    # =========================
    df["ESTNO"] = None

    # 1순위 : 86M / 86R / 86E
    mask = df["ESTNO"].isna()

    df.loc[mask, "ESTNO"] = (
        s[mask]
        .str.extract(r"(86[A-Z])")[0]
    )

    # 2순위 : SIF1215 형태
    mask = df["ESTNO"].isna()

    df.loc[mask, "ESTNO"] = (
        s[mask]
        .str.extract(r"(SIF\d+)")[0]
    )

    # 3순위 : 969G / 270A / 20202EG 형태 (끝 문자가 여러 글자일 수 있음)
    mask = df["ESTNO"].isna()

    df.loc[mask, "ESTNO"] = (
        s[mask]
        .str.extract(r"(\d{2,}[A-Z]+)")[0]
    )

    # 4순위 : 숫자만
    mask = df["ESTNO"].isna()

    df.loc[mask, "ESTNO"] = (
        s[mask]
        .str.extract(r"(\d+)")[0]
    )

    # ACC 예외 처리
    mask = (
        df["ESTNO"].isna()
        &
        s.str.contains("ACC", na=False)
    )

    df.loc[mask, "ESTNO"] = "ACC"

    mask = (
        (df["브랜드"] == "EXCEL")
        &
        (df["등급"] == "PRI")
    )

    df.loc[mask, "등급"] = "UN"

    # =========================
    # 불필요 컬럼 제거
    # =========================
    df = df.drop(
        columns=[
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )

    return df

def eda_added(beige_df,samil_df,sinu_df
              ,aurora_df,eastbelly_df,hyosung_df, daejae_df
              ,huichang_df,swc_df):

    beige_df = beige(beige_df)
    samil_df = samil(samil_df)
    sinu_df = sinu(sinu_df)
    aurora_df = aurora(aurora_df)
    eastbelly_df = eastbelly(eastbelly_df)
    hyosung_df = hyosung(hyosung_df)
    daejae_df = daejae(daejae_df)
    huichang_df = huichang(huichang_df)
    swc_df = swc(swc_df)


    df = pd.concat([beige_df,samil_df,sinu_df
              ,aurora_df,eastbelly_df,hyosung_df, daejae_df
              ,huichang_df,swc_df],ignore_index=True)
    return df