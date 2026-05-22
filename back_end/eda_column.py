import pandas as pd
final_column = [
    "수탁품","규격단위중량","B/L NO식별번호",
    "ESTNO","재고수량","중량","유통기한제조일자","창고"
]

columns_a = [
    "사업부","수탁품[코드]","규격단위중량","단위","LOT-NO직전화주","B/L NO식별번호",
    "ESTNO","저장구역","재고수량","중량","허용수량","담보수량","적재수량","유통기한제조일자","통관구분원산지","창고"

]
columns_b = [
    "사업부","수탁품","품목코드","규격단위중량","단위","LOT-NO직전화주 -->","B/L NO식별번호",
    "ESTNO","저장구역","재고수량","중량","허용수량","담보수량","적재수량","PLT수량","소비기한제조일자","통관구분원산지","창고"
]
columns_c = [
    "사업부","수탁품,[코드]","규격,단위중량","단위","LOT-NO,직전화주","B/L NO,식별번호","ESTNO","저장구역",
    "재고수량","중량","허용수량","담보수량","적재수량","유통기한,제조일자","통관구분,원산지","창고"
]
columns_d = [
    "사업부","수탁품,[코드]","규격","단위","LOT-NO,직전화주","B/L NO,식별번호","ESTNO","저장구역",
    "재고수량","중량","허용수량","담보수량","적재수량","유통기한,제조일자","통관구분,원산지","창고"
]

columns_e = [
    "수탁품,[코드]","브랜드","원산지","등급","ESTNO","규격정보","LOT-NO,직전화주","B/L NO,식별번호","창고","재고수량",
    "총중량","평균중량","유통기한","제조일자","비고","포괄창고"
]

drop_cols = [
    "사업부",
    "LOT-NO",
    "품목코드",
    "LOT-NO직전화주 -->",
    "PLT수량",
    "단위",
    "LOT-NO직전화주",
    "LOT-NO,직전화주",
    "저장구역",
    "허용수량",
    "담보수량",
    "적재수량",
    "통관구분원산지",
    "통관구분,원산지",
    "규격정보",
    "비고",
    "원산지",
    "포괄창고"
]

def beige(df):
    if df is None or df.shape[1] <= 2:
        return print("beige 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def samil(df):
    if df is None or df.shape[1] <= 2:
        return print("samil 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def sinu(df):
    if df is None or df.shape[1] <= 2:
        return print("sinu 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def huichang(df):
    if df is None or df.shape[1] <= 2:
        return print("huichang 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def aurora(df):
    if df is None or df.shape[1] <= 2:
        return print("aurora 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def hyosung(df):
    if df is None or df.shape[1] <= 2:
        return print("hyosung 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def eastbelly(df):
    if df is None or df.shape[1] <= 2:
        return print("eastbelly 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_c
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def swc(df):
    if df is None or df.shape[1] <= 2:
        return print("swc 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_d
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def ch(df):
    if df is None or df.shape[1] <= 2:
        return print("ch 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def daechung(df):
    if df is None or df.shape[1] <= 2:
        return print("daechung 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def daejae(df):
    if df is None or df.shape[1] <= 2:
        return print("daechung 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def hanladt(df):
    if df is None or df.shape[1] <= 2:
        return print("hanladt 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    while len(result.columns) < len(columns_b):
        result[len(result.columns)] = None

    result.columns = columns_b

    result = result.drop(columns=drop_cols, errors="ignore")
    return column_replace(result)
    
def hanla(df):
    if df is None or df.shape[1] <= 2:
        return print("hanla 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    while len(result.columns) < len(columns_b):
        result[len(result.columns)] = None
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)
    
def gangdong1(df):
    if df is None or df.shape[1] <= 2:
        return print("gangdong1 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def gangdong2(df):
    if df is None or df.shape[1] <= 2:
        return print("gangdong2 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def gyungin(df):
    if df is None or df.shape[1] <= 2:
        return print("gyungin 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def plaza(df):
    if df is None or df.shape[1] <= 2:
        return print("plaza 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_a
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def samjin1(df):
    if df is None or df.shape[1] <= 2:
        return print("samjin1 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def samjin2(df):
    if df is None or df.shape[1] <= 2:
        return print("samjin2 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def cs(df):
    if df is None or df.shape[1] <= 2:
        return print("cs 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_b
    result = result.drop(columns = drop_cols, errors = "ignore")
    return column_replace(result)

def jns(df):
    if df is None or df.shape[1] <= 2:
        return print("jns 데이터 없음")  # 또는 return df 그대로
    result = df.copy()
    result.columns = columns_e
    result = result.drop(columns = drop_cols, errors = "ignore")
    col = result.pop("창고")
    result["창고"] = col
    result["창고"] = result["창고"].replace({
        "(주)SWC": "곤SWC",
        "(주)대재냉장": "곤대재",
        "CS냉장": "곤CS",
        "대청냉장(주)": "곤대청",
        "삼진2냉장": "곤삼진2",
    })
    result = result.rename(columns={
        "수탁품,[코드]": "수탁품",
        "B/L NO,식별번호": "B/L NO식별번호",
        "총중량": "중량"
    }, errors="ignore")
    return result

def column_replace(df):
    result = df.copy()
    result = result.rename(columns={
        "수탁품[코드]": "수탁품",
        "수탁품,[코드]": "수탁품",
        "규격,단위중량": "규격단위중량",
        "B/L NO,식별번호": "B/L NO식별번호",
        "소비기한제조일자": "유통기한제조일자",
        "유통기한,제조일자": "유통기한제조일자",
        "통관구분,원산지": "통관구분원산지",
        "규격": "규격단위중량"
    }, errors="ignore")
        
    while len(result.columns) < len(final_column):
        result[len(result.columns)] = None

    result = result.iloc[:, :len(final_column)]

    result.columns = final_column

    return result

def column_split(df):
    added_df_names = [
        "베이지박스투",
        "삼일물류",
        "신우냉장",
        "오로라CS",
        "이스트밸리",
        "효성냉장",
        "희창냉장",
        "SWC"
    ]
    
    six_df_names = [
        "강동1",
        "강동2",
        "경인",
        "삼진1",
        "삼진2",
        "대청",
        "한라",
        "한라 동탄"
    ]

    ch_plz_names = [
        "시에이치물류",
        "프라자로지스"
    ]

    added_df = {
        name: dfs
        for name, dfs in df.items()
        if name in added_df_names
    }

    six_df = {
        name: dfs
        for name, dfs in df.items()
        if name in six_df_names
    }

    ch_plz = {
        name: dfs
        for name, dfs in df.items()
        if name in ch_plz_names
    }

    return added_df, six_df, ch_plz