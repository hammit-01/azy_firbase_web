import logging
import pandas as pd
from back_end.eda_normalize import assign_columns

log = logging.getLogger("eda")

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

columns_f = [
    "사업부","수탁품[코드]","규격단위중량","단위","LOT-NO직전화주","B/L NO식별번호","ESTNO","저장구역","재고수량","중량",
    "허용수량","담보수량","적재수량","유통기한제조일자","통관구분원산지","창고"
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

def _apply_schema(df, schema, name):
    if df is None or df.shape[1] <= 2:
        log.warning(f"[{name}] 데이터 없음 또는 열 부족")
        return pd.DataFrame()
    result = assign_columns(df, schema, name)
    if result.empty:
        return pd.DataFrame()
    result = result.drop(columns=drop_cols, errors="ignore")
    return column_replace(result, name)

def beige(df):
    return _apply_schema(df, columns_a, "베이지박스투")

def samil(df):
    return _apply_schema(df, columns_a, "삼일물류")

def sinu(df):
    return _apply_schema(df, columns_a, "신우냉장")

def huichang(df):
    return _apply_schema(df, columns_a, "희창냉장")

def aurora(df):
    return _apply_schema(df, columns_b, "오로라CS")

def hyosung(df):
    return _apply_schema(df, columns_b, "효성냉장")

def eastbelly(df):
    return _apply_schema(df, columns_c, "이스트밸리")

def swc(df):
    return _apply_schema(df, columns_d, "SWC")

def ch(df):
    return _wms_new_style(df, "시에이치물류")

# 강동/삼진/대청 신규 웹사이트 컬럼 구조 (2026년~)
# raw: 소비기한, 잔여일수, 수탁품, EST NO, 수량, 중량, PLT, B/L NO식별번호, 원산지, 통관구분, 규격, 단위, LOT-NO[직전화주], [저장구역], 담보수량, 사업부, 창고
_wms_rename = {
    "소비기한":  "유통기한제조일자",  # 강동/삼진/한라/경인
    "유통기한":  "유통기한제조일자",  # CH/PLZ/CS
    "EST NO":    "ESTNO",
    "수량":      "재고수량",
    "규격":      "규격단위중량",
}

def _wms_new_style(df, name):
    if df is None or df.shape[1] <= 2:
        print(f"{name} 데이터 없음")
        return pd.DataFrame()
    result = df.rename(columns=_wms_rename, errors="ignore")
    for col in final_column:
        if col not in result.columns:
            result[col] = None
    return result[list(final_column)]

def daechung(df):
    return _wms_new_style(df, "daechung")

def daejae(df):
    return _apply_schema(df, columns_a, "대재")

def hanladt(df):
    return _wms_new_style(df, "hanladt")

def hanla(df):
    return _wms_new_style(df, "hanla")
    
def gangdong1(df):
    return _wms_new_style(df, "gangdong1")

def gangdong2(df):
    return _wms_new_style(df, "gangdong2")

def gyungin(df):
    return _wms_new_style(df, "경인")

def plaza(df):
    return _wms_new_style(df, "프라자로지스")

def samjin1(df):
    return _wms_new_style(df, "samjin1")

def samjin2(df):
    return _wms_new_style(df, "samjin2")

def cs(df):
    return _wms_new_style(df, "CS")

# 아이린냉장 (rtv_stock.do 전용 스키마 — 브랜드/등급/유통기한 컬럼 없음)
# raw: 수탁품, 입고일자, 규격, 단위, LOT-NO, B/L NO, ESTNO, CNTR, 통관, 입고수량, 입고중량, 재고수량, 재고중량, 가공일자
_irn_rename = {
    "규격":     "규격단위중량",
    "B/L NO":  "B/L NO식별번호",
    "재고중량": "중량",
}

def irn(df):
    if df is None or df.shape[1] <= 2:
        log.warning("[아이린냉장] 데이터 없음 또는 열 부족")
        return pd.DataFrame()
    result = df.rename(columns=_irn_rename, errors="ignore")
    for col in final_column:
        if col not in result.columns:
            result[col] = None
    return result[list(final_column)]

def jns(df):
    if df is None or df.shape[1] <= 2:
        return print("jns 데이터 없음")
    result = df.copy()

    # 비고 열 삭제
    result = result.drop(columns=["비고"], errors="ignore")

    # B/L NO + 식별번호 → B/L NO식별번호 (jns_eda 호환)
    if "B/L NO" in result.columns and "식별번호" in result.columns:
        result["B/L NO식별번호"] = (
            result["B/L NO"].astype(str).str.strip() +
            result["식별번호"].astype(str).str.strip()
        )
        result = result.drop(columns=["B/L NO", "식별번호"])

    # 창고명 → 창고 (서브창고 정규화 후 덮어쓰기)
    if "창고명" in result.columns:
        result["창고명"] = result["창고명"].replace({
            "(주)SWC":         "곤SWC",
            "(주)대재냉장":     "곤대재",
            "CS냉장":          "곤CS",
            "대청냉장(주)":     "곤대청",
            "삼진2냉장":        "곤삼진2",
            "에이스냉장(처인)":  "곤에이스처인",
        })
        result["창고"] = result["창고명"]
        result = result.drop(columns=["창고명"])

    # 열 이름 표준화
    result = result.rename(columns={
        "est":      "ESTNO",
        "소비기한": "유통기한",
        "입고일자": "출고일자",
        "총중량":   "중량",
    }, errors="ignore")

    # 수치 정규화
    for col in ["재고수량", "중량", "평균중량"]:
        if col in result.columns:
            result[col] = pd.to_numeric(
                result[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce"
            )

    # 날짜 정규화 (YYYY.MM.DD → YYYY-MM-DD)
    for col in ["유통기한", "출고일자", "제조일자"]:
        if col in result.columns:
            result[col] = pd.to_datetime(
                result[col], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

    return result

def column_replace(df: pd.DataFrame, name: str = "") -> pd.DataFrame:
    result = df.rename(columns={
        "수탁품[코드]":       "수탁품",
        "수탁품,[코드]":      "수탁품",
        "규격,단위중량":      "규격단위중량",
        "B/L NO,식별번호":    "B/L NO식별번호",
        "소비기한제조일자":   "유통기한제조일자",
        "유통기한,제조일자":  "유통기한제조일자",
        "통관구분,원산지":    "통관구분원산지",
        "규격":               "규격단위중량",
    }, errors="ignore")

    for col in final_column:
        if col not in result.columns:
            log.warning(f"[{name}] 필수 컬럼 누락: '{col}' → None 패딩")
            result[col] = None

    return result