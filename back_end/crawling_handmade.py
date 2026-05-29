import pandas as pd
import re
from back_end.eda_column import column_replace

# 고려 냉장
def korea_eda():
    # 엑셀 불러오기
    df = pd.read_excel("./back_end/data/warehouse/고려.xlsx", header=4)
    df = df[df["수탁품명"] != "소     계"]
    df = df[df["수탁품명"] != "합     계"]
    df = df[df["수탁품명"] != "고려종합물류주식회사"]
    df = df[df["수탁품명"] != ""]
    korea = pd.DataFrame()
    korea["수탁품"] = df["수탁품명"].copy()
    korea["평균중량"] = df["규격"].copy()
    korea["재고수량"] = df["재고수량"].copy()
    korea["BL번호"] = df["B/L No."].copy()
    korea["유통기한"] = df["유효기간"].copy()
    korea["창고"] = "고려"
    korea = korea.dropna(subset=['수탁품'])
    korea[['브랜드', '수탁품', '등급', 'ESTNO']] = (
        korea['수탁품'].apply(parse_koryo_case)
    )

    return korea

# 에이스기흥
def aceGH_eda():
    # 엑셀 불러오기
    df = pd.read_excel("./back_end/data/warehouse/에이스기흥.xlsx", header=4)
    df = df[df["수탁품"] != "소     계"]
    df = df[df["수탁품"] != "합     계"]
    df = df[df["수탁품"] != ""]
    aceGH = pd.DataFrame()
    aceGH["수탁품"] = df["수탁품"].copy()
    aceGH["평균중량"] = ""
    aceGH["재고수량"] = df["현재고"].copy()
    aceGH["BL번호"] = df["BL-NO"].copy()
    aceGH["유통기한"] = df["유통기한"].copy()
    aceGH["ESTNO"] = df["EST-NO"].copy()
    aceGH["창고"] = "에이스기흥"
    aceGH = aceGH.dropna(subset=['수탁품'])
    aceGH[['수탁품', '등급']] = (
        aceGH['수탁품'].apply(parse_product_aceGH)
    )

    return aceGH

# 에이스처인
def aceCHIN_eda():
    # 엑셀 불러오기
    df = pd.read_excel("./back_end/data/warehouse/에이스처인.xlsx", header=4)
    df = df[df["수탁품"] != "소     계"]
    df = df[df["수탁품"] != "합     계"]
    df = df[df["수탁품"] != ""]
    aceCHIN = pd.DataFrame()
    aceCHIN["수탁품"] = df["수탁품"].copy()
    aceCHIN["평균중량"] = ""
    aceCHIN["재고수량"] = df["현재고"].copy()
    aceCHIN["BL번호"] = df["BL-NO"].copy()
    aceCHIN["유통기한"] = df["유통기한"].copy()
    aceCHIN["ESTNO"] = df["EST-NO"].copy()
    aceCHIN["창고"] = "에이스처인"
    aceCHIN = aceCHIN.dropna(subset=['수탁품'])
    aceCHIN[['브랜드', '수탁품', '등급']] = (
        aceCHIN['수탁품'].apply(parse_product_ace)
    )

    return aceCHIN

# 에이스용인
def aceYOGIN_eda():
    # 엑셀 불러오기
    df = pd.read_excel("./back_end/data/warehouse/에이스용인.xlsx", header=4)
    df = df[df["수탁품"] != "소     계"]
    df = df[df["수탁품"] != "합     계"]
    df = df[df["수탁품"] != ""]
    aceYOGIN = pd.DataFrame()
    aceYOGIN["수탁품"] = df["수탁품"].copy()
    aceYOGIN["평균중량"] = ""
    aceYOGIN["재고수량"] = df["현재고"].copy()
    aceYOGIN["BL번호"] = df["BL-NO"].copy()
    aceYOGIN["유통기한"] = df["유통기한"].copy()
    aceYOGIN["ESTNO"] = df["EST-NO"].copy()
    aceYOGIN["창고"] = "에이스용인"
    aceYOGIN = aceYOGIN.dropna(subset=['수탁품'])
    aceYOGIN[['브랜드', '수탁품', '등급']] = (
        aceYOGIN['수탁품'].apply(parse_product_ace)
    )
    
    return aceYOGIN

# 유상
def yousang_eda():
    # 엑셀 불러오기
    df = pd.read_excel("./back_end/data/warehouse/유상.xlsx", header=[6,7])
    df.columns = [
        '_'.join([str(c) for c in col if 'Unnamed' not in str(c)])
        for col in df.columns
    ]
    df = df.loc[:, ~df.columns.duplicated()]
    df = df[df["수탁품명"] != "소     계"]
    df = df[df["수탁품명"] != "합     계"]
    df = df[df["수탁품명"] != "(주)유상"]
    yousang = pd.DataFrame()
    yousang["수탁품"] = df["수탁품명"].copy()
    yousang["평균중량"] = df["규격_단위"].copy()
    yousang["재고수량"] = df["재고수량 / 재고중량_재고"].copy()
    yousang["BL번호"] = df["B/L No._상대코드."].copy()
    yousang["유통기한"] = (
        pd.to_datetime(df["가공일자_유효기간"])
        + pd.Timedelta(days=730)
    ).dt.strftime("%Y-%m-%d")
    yousang["브랜드"] = df["브랜드_콘테이너 No."].copy()
    yousang["창고"] = "유상"
    
    yousang = yousang.dropna(subset=['수탁품'])
    yousang[['수탁품', 'ESTNO']] = yousang['수탁품'].apply(parse_product_yousang)

    return yousang

# 견우오아시스
def kyunu_eda():
    # 엑셀 불러오기    
    df = pd.read_excel("./back_end/data/warehouse/견우오아시스.xlsx", header=4)
    df = df[df["수탁품명"] != "소     계"]
    df = df[df["수탁품명"] != "합     계"]
    df = df[df["수탁품명"] != "(주)견우푸드 오아시스지점"]

    kyunu = pd.DataFrame()
    kyunu["수탁품"] = df["수탁품명"].copy()
    kyunu["평균중량"] = df["규격"].copy()
    kyunu["재고수량"] = df["재고수량"].copy()
    kyunu["BL번호"] = df["B/L No."].copy()
    kyunu["유통기한"] = df["유효기간"].copy()
    kyunu["브랜드"] = df["브랜드"].copy()
    kyunu["창고"] = "견우오아시스"

    kyunu = kyunu.dropna(subset=['수탁품'])
    kyunu[['수탁품', '등급', 'ESTNO']] = kyunu['수탁품'].apply(parse_product_kyunu)

    return kyunu

# 견우 오아시스
def parse_product_kyunu(text):
    pattern = r'^(.*?)\s*\((.*?)\)\s*([A-Z]+)/(.*)$'
    match = re.match(pattern, text)

    if match:
        return pd.Series({
            '수탁품': match.group(1).strip(),
            '등급': match.group(3).strip(),
            'ESTNO': match.group(4).strip()
        })
    else:
        return pd.Series({
            '수탁품': None,
            '등급': None,
            'ESTNO': None
        })

# 유상
def parse_product_yousang(text):

    if pd.isna(text):
        return pd.Series({
            '수탁품': None,
            'ESTNO': None
        })

    text = str(text).strip()

    # 수탁품 추출
    product_match = re.match(r'^([가-힣A-Za-z]+)', text)

    # E.숫자 추출
    estno_match = re.search(r'E\.(\d+)', text)

    return pd.Series({
        '수탁품': product_match.group(1) if product_match else None,
        'ESTNO': estno_match.group(1) if estno_match else None
    })

# 에이스
def parse_product_ace(text):

    if pd.isna(text):
        return pd.Series({
            '브랜드': None,
            '수탁품': None,
            '등급': None,
            'ESTNO': None
        })

    text = str(text).strip()

    if ")" not in text:
        return pd.Series({
            '브랜드': None,
            '수탁품': None,
            '등급': None,
            'ESTNO': None
        })

    brand, rest = text.split(")", 1)
    parts = rest.strip().split()

    if not parts:
        return pd.Series({
            '브랜드': brand,
            '수탁품': None,
            '등급': None,
            'ESTNO': None
        })

    grade = None
    product = None

    # CASE 1: 마지막이 등급
    if len(parts) >= 2:
        grade = parts[-1]
        product = " ".join(parts[:-1])
    else:
        product = parts[0]

    return pd.Series({
        '브랜드': brand,
        '수탁품': product,
        '등급': grade
    })

# 에이스기흥
def parse_product_aceGH(text):

    if pd.isna(text):
        return pd.Series({'수탁품': None, '등급': None, 'ESTNO': None})

    text = str(text).strip()

    # 1) ESTNO 분리
    estno = None
    if "/est." in text:
        text, estno = text.split("/est.", 1)
        estno = estno.strip()

    # 2) 브랜드 제거 (있으면)
    if " " in text and ")" in text:
        text = text.split(")", 1)[-1]

    # 3) 등급 분리 (" 기준)
    grade = None
    product = text

    if '"' in text:
        product, grade = text.split('"', 1)
        grade = grade.strip() if grade else None

    product = product.strip()
    product = re.sub(r'^[A-Z/]+\)', '', product)

    return pd.Series({
        '수탁품': product,
        '등급': grade
    })

def parse_koryo_case(text):

    if pd.isna(text):
        return pd.Series({'브랜드': None, '수탁품': None, '등급': None, 'ESTNO': None})

    text = str(text).strip()

    # 1. 브랜드 (마지막 )
    if ")" in text:
        left, brand = text.rsplit(")", 1)
    else:
        left, brand = text, None

    brand = brand.strip() if brand else None

    # 2. (4025897) 제거
    left = re.sub(r'\([A-Z]*\)', '', left)

    # 3. ESTNO + 나머지
    m = re.match(r'^(\d+[A-Z]?)\s*(.*)$', left)
    if m:
        estno = m.group(1)
        rest = m.group(2).strip()
    else:
        estno = None
        rest = left

    # 4. 등급 + 수탁품
    m = re.match(r'^([A-Z\-]{1,5})\s*(.*)$', rest)
    grade = m.group(1)
    product = m.group(2).strip()

    return pd.Series({
        '브랜드': brand,
        '수탁품': product,
        '등급': grade,
        'ESTNO': estno
    })


def crawling_handmade():
    result = pd.concat([korea_eda(),aceGH_eda(),aceCHIN_eda(),aceYOGIN_eda(),yousang_eda(),kyunu_eda()], ignore_index=True)

    result["평균중량"] = (
        result["평균중량"]
        .astype(str)
        .str.extract(r"([\d.]+)")[0]
        .astype(float)
    )

    result["유통기한"] = (
        pd.to_datetime(result["유통기한"])
        .dt.strftime("%Y.%m.%d")
    )
    return result