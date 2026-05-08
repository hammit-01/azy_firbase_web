import re
import pandas as pd

def ch_eda(ch):
    ch = ch.drop_duplicates()

    ch["창고"] = "ch"

    ch[["유통기한", "제조일자"]] = (ch["소비기한제조일자"].apply(split_dates))

    ch["평균중량"] = ch["규격단위중량"].str.extract(r'(\d+\.\d+)')

    # 브랜드 추출
    ch["브랜드"] = ch["수탁품"].str.extract(r"-([A-Z]+)$")

    ch = name_eda(ch)

    ch[["BL번호", "이력번호"]] = ch["B/L NO식별번호"].apply(split_history)
    ch = ch.drop(columns=["B/L NO식별번호", "소비기한제조일자", "담보수량", "허용수량", "규격단위중량"], errors="ignore")

    return ch


def plz_eda(plz):
    plz = plz.drop_duplicates()

    plz["창고"] = "프라자"

    # 유통기한 추출
    plz["유통기한"] = plz["소비기한제조일자"].str.replace(r"\.\s+\.$", "", regex=True)
    plz["제조일자"] = ""

    # 브랜드 추출
    plz["브랜드"] = plz["규격단위중량"].str.extract(r"([A-Z]+)")

    # 중량 추출
    plz["평균중량"] = plz["규격단위중량"].str.extract(r"(\d+(?:\.\d+)?)KG")

    # 숫자형 변환
    plz["평균중량"] = plz["평균중량"].astype(float)
    
    plz = name_eda(plz)

    plz[["BL번호", "이력번호"]] = plz["B/L NO식별번호"].apply(split_history)
    plz = plz.drop(columns=["B/L NO식별번호", "소비기한제조일자", "담보중량", "허용수량", "담보수량", "규격단위중량"], errors="ignore")
    
    return plz

# 유통기한
def split_dates(text):

    text = str(text).strip()

    # 날짜 2개 추출
    dates = re.findall(r"\d{4}\.\d{2}\.\d{2}", text)

    if len(dates) >= 2:
        return pd.Series([dates[0], dates[1]])

    elif len(dates) == 1:
        return pd.Series([dates[0], ""])

    else:
        return pd.Series(["", ""])

# BL번호 / 이력번호 분리
def split_history(text):

    text = str(text).strip()

    # 길이가 15 미만이면
    if len(text) < 17:
        return pd.Series([text, ""])

    # 뒤 12자리 = 이력번호
    history_no = text[-12:]

    # 앞부분 = BL번호
    bl_no = text[:-12]

    return pd.Series([bl_no, history_no])


# 규격 추출
def extract_spec(text):
    
    text = str(text)

    m = re.search(
        r"([A-Z]+(?:\s[A-Z]+)?/[A-Z0-9]+)",
        text
    )

    return m.group(1).strip() if m else None

# 부위명 추출
def extract_part(text):
    text = re.sub(r"#\d+-?[A-Z]?", "", text)
    text = re.sub(r"\(우\)", "", text)
    text = re.sub(r"\(\d+\)", "", text)
    text = re.sub(r"-.*", "", text)

    # 규격 제거
    text = re.sub(r"[A-Z]+/?\d*[A-Z]*", "", text)

    return text.strip("/ ")

# 이름 열 나누기
def name_eda(df):
    df["수탁품"] = df["수탁품"].str.replace(r'\[.*?\]', '', regex=True)

    # 수탁품 열 전처리
    # [] 제거
    df["수탁품"] = (
        df["수탁품"]
        .str.replace(r"\[.*?\]", "", regex=True)
        .str.strip()
    )


    df["규격"] = df["수탁품"].apply(extract_spec)

    df[["등급", "ESTNO"]] = (
        df["규격"]
        .str.split("/", n=1, expand=True)
    )

    df["등급"] = df["등급"].str.strip()
    df["ESTNO"] = df["ESTNO"].str.strip()

    df["수탁품"] = df["수탁품"].apply(extract_part)

    df = df.drop(columns=["규격"], errors="ignore")

    return df