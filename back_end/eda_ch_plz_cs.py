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

    # 슬래시 구분된 파트들: 첫 파트=등급, 마지막 파트=ESTNO
    # XT/278, UN/245E, XT/UN/245E 모두 처리
    m = re.search(r"([A-Z][A-Z0-9]*(?:/[A-Z0-9]+)+)", text)

    if not m:
        return pd.Series([None, None, None])

    parts = m.group(0).split("/")
    grade = parts[0]
    raw_est = parts[-1]
    brand = None

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

    # 등급 없이 숫자만 있는 경우 (예: "()104") — 프라자 WMS는 브라질산 육류의
    # SIF(위생감독청) 코드를 "SIF" 글자 없이 숫자만 적어놓음 — 원본엔 없지만
    # 정식 EST 번호 표기는 SIF+숫자이므로 붙여서 복원.
    m = re.search(r"(\d+)", text)
    if m:
        return pd.Series([
            None,
            f"SIF{m.group(1)}"   # ESTNO
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

    # 평균중량: 한글 포함 행(메모 텍스트)은 None, 나머지는 숫자 추출
    _spec = ch["규격단위중량"].astype(str)
    ch["평균중량"] = pd.to_numeric(
        _spec.str.extract(r"([\d.]+)")[0],
        errors="coerce"
    )
    ch.loc[_spec.str.contains("[가-힣]", regex=True, na=False), "평균중량"] = None

    ch["브랜드"] = (
        ch["기타정보"]
        .astype(str)
        .str.extract(r"-([A-Z]+)(?:\[|$)")[0]
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

    _spec = plz["규격단위중량"].astype(str)

    # 브랜드: 알파벳 시작 부분 추출 (SWIFT, EXCEL 등)
    plz["브랜드"] = _spec.str.extract(r"^([A-Za-z]+)")[0]

    # 평균중량: KG 포함 경우만 (단순 숫자=규격코드는 제외)
    plz["평균중량"] = pd.to_numeric(
        _spec.str.extract(r"(\d+(?:\.\d+)?)\s*[Kk][Gg]")[0],
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

def cs_eda(data):
    if data is None or data.empty:
        return data

    cs = data.drop_duplicates().copy()

    cs["창고"] = "CS"

    cs["기타정보"] = cs["기타정보"].str.replace("()", "", regex=False)
    cs["기타정보"] = cs["기타정보"].str.replace("/", "", regex=False)
    cs["기타정보"] = cs["기타정보"].str.replace("[000000]", "", regex=False)

    cs["평균중량"] = (
        cs["규격단위중량"]
        .astype(str)
        .str.extract(r'(\d+(?:\.\d+)?)')[0]
        .astype(float)
    )

    cs[['등급', '브랜드', 'ESTNO']] = cs['기타정보'].apply(split_data)

    # 원본 제거
    cs = cs.drop(
        columns=['기타정보', '규격단위중량'],
        errors='ignore'
    )

    return cs

# =========================
# 아이린냉장 EDA
# =========================
def irn_eda(data):
    if data is None or data.empty:
        return data

    irn = data.drop_duplicates().copy()

    irn["창고"] = "아이린냉장"
    # 브랜드/등급이 상품명에 뭉쳐 있고 분리 규칙이 아직 불확실 — 우선 비워둠
    irn["브랜드"] = ""
    irn["등급"] = ""
    irn["평균중량"] = None

    # 브랜드/등급 미추출 — eda_common이 만든 기타정보(비한글 텍스트)는 사용하지 않고 버림
    irn = irn.drop(columns=["규격단위중량", "기타정보"], errors="ignore")

    return irn


def split_data(text):
    # 등급 추출 ("..." 형태)
    grade = ''
    m = re.search(r'"([^"]+)"', text)
    if m:
        grade = m.group(1).replace('/', '')

    # 브랜드 추출 (... )
    brand = ''
    m = re.search(r'\(([^()]*)\)\[', text)
    if m:
        brand = m.group(1)

    # ESTNO 추출 [...]
    estno = ''
    m = re.search(r'\[([^\]]+)\]', text)
    if m:
        estno = m.group(1)

    return pd.Series([grade, brand, estno])
