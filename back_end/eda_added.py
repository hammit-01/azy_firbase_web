import pandas as pd
import re

def huichang(data):
    if data is None or data.empty:
        return pd.DataFrame()
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()
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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()
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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()
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

    # 브랜드는 rtv_stock.do 자체엔 없어서 crawler.py가 rtv_stock02.do에서 별도로
    # 조회해 채워둔 값을 그대로 씀(괄호 부분은 거기서 이미 제거됨) — 매칭 실패한
    # 행만 빈 값으로 남음
    df["브랜드"] = df["브랜드"].fillna("") if "브랜드" in df.columns else ""

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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()
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

_DAEJAE_GRADE_RE = re.compile(r"(SE|CH|PS|PR)")
_DAEJAE_BRAND_RE = re.compile(
    r"(SHOWCASE\(5STAR\)|5STAR|EXCEL|SADIA|INCARLOPSA|PERDIGAO|PPCS|SWIFT|SEARA|NATIONAL)"
)
_DAEJAE_PAREN_RE = re.compile(r"\(.*?\)")
_DAEJAE_ALNUM_RE = re.compile(r"^[A-Za-z0-9]*$")

def _parse_daejae_info(text):
    """기타정보에서 [상품코드 접두어][등급][브랜드][ESTNO]를 브랜드 위치를 기준으로 분리.
    화이트리스트로 ESTNO를 통째로 매칭하던 예전 방식은 새 코드가 나올 때마다
    계속 놓쳤음(267/208A/3D 실종 사고) — 브랜드 뒤에 남는 부분을 그대로 ESTNO로
    쓰면 화이트리스트 없이도 새 코드에 자동 대응된다.
    등급 앞에 남는 접두어(예: "알목심BS"의 "BS")는 상품명에서 잘못 떨어져 나온
    것이므로 상품명에 다시 붙여준다."""
    b = _DAEJAE_BRAND_RE.search(text)
    if not b:
        return "", None, None, None
    prefix = text[:b.start()]
    brand = b.group(1)

    g = _DAEJAE_GRADE_RE.search(prefix)
    if g:
        grade = g.group(1)
        name_prefix = prefix[:g.start()]
    else:
        grade = None
        name_prefix = ""
    if not _DAEJAE_ALNUM_RE.match(name_prefix):
        # 영숫자가 아닌 잡음(괄호 등)이면 상품명에 붙이지 않고 버림
        name_prefix = ""

    estno = _DAEJAE_PAREN_RE.sub("", text[b.end():]).strip()
    return name_prefix, grade, brand, (estno or None)


def daejae(data):
    if data is None or data.empty:
        return pd.DataFrame()

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()

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

    parsed = s.apply(_parse_daejae_info)
    df["등급"]  = parsed.apply(lambda t: t[1])
    df["브랜드"] = parsed.apply(lambda t: t[2])
    df["ESTNO"] = parsed.apply(lambda t: t[3])

    name_prefix = parsed.apply(lambda t: t[0])
    has_prefix = name_prefix.astype(bool)
    df.loc[has_prefix, "수탁품"] = (
        df.loc[has_prefix, "수탁품"].astype(str) + name_prefix[has_prefix]
    )



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

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()

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
    # 등급 + ESTNO 폴백 (부채살/탕갈비 등)
    # 대부분 상품은 "브랜드+임의숫자코드+ESTNO" 구조라 등급이 아예 없는데,
    # 일부는 "브랜드+임의숫자코드+등급+ESTNO"로 한 토큰 더 있어서(예: SWIFT6571CHO969)
    # 위 화이트리스트로 못 찾음. 위에서 여전히 못 찾은 행만: 브랜드(맨 앞 영문)와
    # 숫자코드(그 다음 숫자열)를 떼어내고, 남은 부분 앞쪽 영문 구간을 등급,
    # 나머지를 ESTNO로 잡는다. 화이트리스트/SIF로 이미 잡힌 행은 안 건드림.
    # =================================================
    mask_still_no_est = df["ESTNO"].isna()
    if mask_still_no_est.any():
        remainder = (
            df.loc[mask_still_no_est, "기타정보"]
            .astype(str)
            .str.replace(r"^[A-Z]+", "", regex=True)
            .str.replace(r"^\d{4}", "", regex=True)  # 임의숫자4자리 코드만 떼어냄(ESTNO 앞자리 숫자까지 먹지 않도록)
        )
        fallback = remainder.str.extract(r"^([A-Z]+)(.+)$")
        df.loc[mask_still_no_est, "등급"] = fallback[0]
        estno_fallback = fallback[1].where(fallback[1].astype(str).str.strip() != "", None)
        df.loc[mask_still_no_est, "ESTNO"] = estno_fallback

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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()
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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()

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
    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()

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
    _SWC_KNOWN_BRANDS = r"EXCEL|SWIFT|SADIA|IBP|TEYS|AMH|KILCOY|SHOWCASE|ACC|TONNIES|SEARA"

    df["브랜드"] = s.str.extract(
        rf"({_SWC_KNOWN_BRANDS})"
    )[0]

    # 화이트리스트에 없는 새 브랜드 대응 — 등급/브랜드가 구분자 없이 붙어 있어
    # (예: AASA06-012100) 알려진 브랜드가 하나도 안 걸리면, 맨 앞 대문자 연속
    # 구간 중 숫자/하이픈 직전까지를 브랜드로 처리
    mask = df["브랜드"].isna()
    df.loc[mask, "브랜드"] = (
        s[mask]
        .str.extract(r"^([A-Z]+)(?=[\d-])")[0]
    )

    # =========================
    # 등급
    # =========================
    # 원본 공백이 상위 단계(eda_common)에서 전부 제거돼 브랜드와 등급이 "EXCELSEL"
    # 처럼 구분자 없이 붙는다. 그래서 (1) 아는 브랜드를 앞에서 먼저 잘라낸 뒤
    # (2) 나머지에서 단어 경계로 등급을 찾는다 — 이렇게 해야 "EXCEL SEL"의 SEL은
    # 살리면서 "SEARA"(브랜드) 안의 "SE"는 오탐하지 않는다 (2026-08-12,
    # 닭장각정육/SEARA에 없는 등급 SE가 잡히던 버그 + 단순 단어경계 앵커만 걸었을
    # 때 EXCEL/SEL, KILCOY/GF 등 정상 등급까지 같이 사라지던 회귀 모두 확인).
    s_no_brand = s.str.replace(rf"^(?:{_SWC_KNOWN_BRANDS})", "", regex=True)
    df["등급"] = s_no_brand.str.extract(
        r"(?<![A-Za-z])(ANGUS_CH|SEL|PRI|PRE|CH|GF|SE|UN)(?![A-Za-z])"
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