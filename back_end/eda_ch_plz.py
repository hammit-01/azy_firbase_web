import re
import pandas as pd


# =========================
# CH 규격 추출
# =========================
def extract_spec_ch(data):

    text = str(data)

    # 앞 () 제거
    text = re.sub(r"^\(\)", "", text)

    # 앞 숫자 제거
    text = re.sub(r"^\d+", "", text)

    # 기본 패턴
    m = re.search(
        r"([A-Z]+)/([A-Z0-9]+)(?:\(\d+\))?([A-Z]+)?",
        text
    )

    if not m:
        return pd.Series([None, None, None])

    grade = m.group(1)

    raw_est = m.group(2)

    brand = m.group(3)

    # 1311SWIFT 같은 케이스 처리
    split_m = re.match(
        r"(\d+[A-Z]?)([A-Z]{2,})$",
        raw_est
    )

    if split_m:

        estno = split_m.group(1)

        if not brand:
            brand = split_m.group(2)

    else:
        estno = raw_est

    return pd.Series([
        grade,
        estno,
        brand
    ])


# =========================
# 프라자 규격 추출
# =========================
def extract_spec_plz(data):

    text = str(data)

    m = re.search(
        r"([A-Z]+)/([A-Z0-9]+)",
        text
    )

    if m:

        return pd.Series([
            m.group(1),  # 등급
            m.group(2)   # ESTNO
        ])

    return pd.Series([
        None,
        None
    ])


# =========================
# 부위명 추출
# =========================
def extract_part(data):

    text = str(data)

    # #123 제거
    text = re.sub(
        r"#\d+-?[A-Z]?",
        "",
        text
    )

    # (123) 제거
    text = re.sub(
        r"\(\d+\)",
        "",
        text
    )

    # - 이후 제거
    text = re.sub(
        r"-.*",
        "",
        text
    )

    # 규격 제거
    text = re.sub(
        r"[A-Z]+/?\d*[A-Z]*",
        "",
        text
    )

    return text.strip("/ ")


# =========================
# CH 이름 EDA
# =========================
def name_eda_ch(data):

    df = data.copy()

    # 수탁품 정리
    df["수탁품"] = (
        df["수탁품"]
        .astype(str)
        .str.replace(
            r"\[.*?\]",
            "",
            regex=True
        )
        .str.strip()
    )

    # 규격 추출
    tmp = df["기타정보"].apply(extract_spec_ch)

    df["등급"] = tmp[0]
    df["ESTNO"] = tmp[1]

    # 문자열 정리
    for col in ["등급", "ESTNO"]:

        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df[col] = df[col].replace("", None)

    # 부위명 정리
    df["수탁품"] = (
        df["수탁품"]
        .apply(extract_part)
    )

    return df


# =========================
# 프라자 이름 EDA
# =========================
def name_eda_plz(data):

    df = data.copy()

    # 수탁품 정리
    df["수탁품"] = (
        df["수탁품"]
        .astype(str)
        .str.replace(
            r"\[.*?\]",
            "",
            regex=True
        )
        .str.strip()
    )

    # 규격 추출
    tmp = df["기타정보"].apply(extract_spec_plz)

    df["등급"] = tmp[0]
    df["ESTNO"] = tmp[1]

    # 문자열 정리
    for col in ["등급", "ESTNO", "브랜드"]:

        if col in df.columns:

            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            df[col] = df[col].replace("", None)

    # 부위명 정리
    df["수탁품"] = (
        df["수탁품"]
        .apply(extract_part)
    )

    return df


# =========================
# CH EDA
# =========================
def ch_eda(data):
    if data is None or data.empty:
        return
    ch = data.drop_duplicates().copy()

    ch["창고"] = "CH"

    # 1. 전산이체 제거
    ch["평균중량"] = (
        ch["규격단위중량"]
        .astype(str)
        .str.replace("전산이체", "", regex=False)
        .str.strip()
    )

    # 2. 숫자만 추출 (KG 제거 + float 변환)
    ch["평균중량"] = (
        ch["평균중량"]
        .str.extract(r"([\d.]+)")
        .astype(float)
    )
    
    ch["브랜드"] = (
        ch["기타정보"]
        .astype(str)
        .str.extract(r"-([A-Z]+)\[")[0]
    )

    # 이름 EDA
    ch = name_eda_ch(ch)

    # 불필요 컬럼 제거
    ch = ch.drop(
        columns=[
            "B/L NO식별번호",
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )

    return ch


# =========================
# 프라자 EDA
# =========================
def plz_eda(data):
    if data is None or data.empty:
        return
    plz = data.drop_duplicates().copy()

    plz["창고"] = "프라자"

    # 브랜드 추출
    tmp = (
        plz["규격단위중량"]
        .astype(str)
        .str.extract(
            r"([A-Z가-힣]+)(\d+(?:\.\d+)?)"
        )
    )

    plz["브랜드"] = tmp[0]

    # 평균중량
    plz["평균중량"] = pd.to_numeric(
        tmp[1],
        errors="coerce"
    )

    # 이름 EDA
    plz = name_eda_plz(plz)

    # 불필요 컬럼 제거
    plz = plz.drop(
        columns=[
            "B/L NO식별번호",
            "규격단위중량",
            "기타정보"
        ],
        errors="ignore"
    )


    return plz