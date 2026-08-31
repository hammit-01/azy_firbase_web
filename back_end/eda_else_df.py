import numpy as np
import pandas as pd


# =========================================================
# 강동
# =========================================================
def kd_eda(data):
    if data is None or data.empty:
        return

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    df = data.copy()

    # () 제거
    df["기타정보"] = (
        df["기타정보"]
        .astype(str)
        .str.replace("()", "", regex=False)
    )

    # -------------------------------------------------
    # 등급
    # -------------------------------------------------
    df["등급"] = (
        df["기타정보"]
        .astype(str)
        .str.extract(r"^([^/]+)")[0]
    )

    # / 시작이면 등급 없음
    df.loc[
        df["기타정보"].astype(str).str.startswith("/"),
        "등급"
    ] = None

    # 강동2: 냉장 표시가 상품명이 아니라 규격(규격단위중량)에 "냉장EXCEL"처럼
    # 브랜드 앞에 붙어서 옴 — 안 떼면 아래 브랜드/평균중량 정규식이 ^로 시작을
    # 강제해서 통째로 매칭 실패한다(2026-08-12, 브랜드=NaN, 평균중량=NaN으로
    # 깨지던 것 라이브 데이터로 확인). 다른 창고처럼 상품명 앞으로 옮기고 규격
    # 값에서는 뗀다.
    냉장_spec_mask = df["규격단위중량"].astype(str).str.startswith("냉장")
    df.loc[냉장_spec_mask, "수탁품"] = "냉장" + df.loc[냉장_spec_mask, "수탁품"].astype(str)
    df.loc[냉장_spec_mask, "규격단위중량"] = (
        df.loc[냉장_spec_mask, "규격단위중량"]
        .astype(str)
        .str.replace(r"^냉장", "", regex=True)
    )

    # -------------------------------------------------
    # 브랜드
    # WINGHAM15.57KG -> WINGHAM
    # SADIA/BRF12KG -> SADIA
    # -------------------------------------------------
    df["브랜드"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"^([A-Za-z/]+)")[0]
        .str.split("/")
        .str[0]
    )

    # 평균중량
    df["평균중량"] = (
        df["규격단위중량"]
        .astype(str)
        .str.extract(r"(\d+(?:\.\d+)?)")[0]
        .astype(float)
    )

    # 규격단위중량에 브랜드만 있고 숫자(중량)가 아예 없는 로트(예: "SMITHFIELD")는
    # 위 추출이 NaN으로 빠진다 — 총중량÷재고수량으로 대체 계산(hl_eda와 동일 방식,
    # 2026-08-31 강동1/2 평중 누락 발견).
    missing = df["평균중량"].isna()
    if missing.any():
        _weight = pd.to_numeric(df["중량"].astype(str).str.replace(",", "", regex=False), errors="coerce")
        _qty = pd.to_numeric(df["재고수량"].astype(str).str.replace(",", "", regex=False), errors="coerce")
        df.loc[missing, "평균중량"] = (_weight / _qty).round(2)[missing]

    # -------------------------------------------------
    # 기타정보 제거
    # -------------------------------------------------
    df = df.drop(
        columns=["기타정보"],
        errors="ignore"
    )

    return df


# =========================================================
# 경인 / 삼진
# =========================================================
def ki_eda(data1):
    if data1 is None or data1.empty:
        return data1

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    ki = data1.copy()

    # =====================================================
    # 1. 경인 (ki)
    # =====================================================
    d = ki.copy()

    s = d["기타정보"].astype(str)

    # -------------------------------------------------
    # 등급
    # A(SOUTHERN)180 -> A
    # -------------------------------------------------
    d["등급"] = s.str.extract(r"^([A-Za-z])")[0]

    # -------------------------------------------------
    # 브랜드
    # (SOUTHERN)
    # -------------------------------------------------
    d["브랜드"] = s.str.extract(r"\((.*?)\)")[0]

    # -------------------------------------------------
    # ESTNO
    # 마지막 숫자 (기타정보 우선, 없으면 수탁품에서 폴백)
    # -------------------------------------------------
    d["ESTNO"] = s.str.extract(r"(\d+[A-Za-z]*)$")[0]
    null_est = d["ESTNO"].isna()
    if null_est.any():
        d.loc[null_est, "ESTNO"] = (
            d.loc[null_est, "수탁품"]
            .astype(str)
            .str.extract(r"(\d+[A-Za-z]*)$")[0]
        )

    # 브랜드 폴백: 기타정보에서 못 찾으면 수탁품 괄호에서 추출
    null_brand = d["브랜드"].isna()
    if null_brand.any():
        d.loc[null_brand, "브랜드"] = (
            d.loc[null_brand, "수탁품"]
            .astype(str)
            .str.extract(r"\(([^()]+)\)")[0]
        )

    # 평균중량
    s = (
        d["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    d["평균중량"] = (
        s.str.extract(r"^(.*?)(?=[A-Z])")[0]
        .astype(float)
    )

    # -------------------------------------------------
    # 기타정보 제거
    # -------------------------------------------------
    ki = d.drop(
        columns=["기타정보"],
        errors="ignore"
    )

    return ki

def sjn_eda(data1):
    if data1 is None or data1.empty:
            return

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    sjn = data1.copy()
    # =====================================================
    # 2. 삼진 (sjn)
    # =====================================================
    d2 = sjn.copy()

    s2 = d2["기타정보"].astype(str)

    # -------------------------------------------------
    # 전처리
    # ★ 제거
    # -------------------------------------------------
    s2 = (
        s2.str.replace("★", "", regex=False)
          .str.replace("☆", "", regex=False)
    )

    # -------------------------------------------------
    # 브랜드
    # ()(EXCEL)CH#86M -> EXCEL
    # -------------------------------------------------
    d2["브랜드"] = (
        s2.str.extract(r"\(([^()]+)\)")[0]
    )

    # -------------------------------------------------
    # 등급
    # ()(TEYS)UN_294 -> UN  /  ()YP/GF(KILCOY)640 -> GF (구분자가 ) 아닌 / 인 경우도 있음)
    # 등급 코드(1~2글자)는 항상 숫자/밑줄/브랜드 괄호 앞에 붙어 나옴 — 그렇지 않은 경우
    # (예: ()(AMP)HELLABY 같은 브랜드/공장명 전용 표기)는 등급 없음으로 처리
    # -------------------------------------------------
    d2["등급"] = s2.str.extract(
        r"(?<![A-Za-z])([A-Za-z]{1,2})(?=[\d_(])"
    )[0]

    # -------------------------------------------------
    # ESTNO
    # _294 -> 294  /  SE86M -> 86M (선두 등급코드 제거)
    # 숫자가 전혀 없는 값(브랜드/공장명이 그대로 딸려온 경우)은 ESTNO 아님 → 제외
    # -------------------------------------------------
    estno = (
        d2["기타정보"]
        .astype(str)
        .str.extract(r"[)_]([^)_]+)$")[0]
        .str.replace(r"^[A-Z]{1,2}(?=\d)", "", regex=True)
    )
    d2["ESTNO"] = estno.where(estno.str.contains(r"\d", na=False), None)

    # 평균중량
    s = (
        d2["규격단위중량"]
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    d2["평균중량"] = (
        s.str.extract(r"^(.*?)(?=[A-Z])")[0]
        .astype(float)
    )

    # -------------------------------------------------
    # 기타정보 제거
    # -------------------------------------------------
    sjn = d2.drop(
        columns=["기타정보"],
        errors="ignore"
    )

    return sjn


# =========================================================
# 대청
# =========================================================
def dch_eda(data):
    if data is None or data.empty:
        return

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    dch = data.copy()

    s = dch["기타정보"].fillna("").astype(str)

    # -----------------------------------
    # 1. 특수문자 제거
    # -----------------------------------
    s = s.str.replace(r"[♥☆★\(\)]", "", regex=True)

    # -----------------------------------
    # 2. 브랜드 추출 (기본)
    # -----------------------------------
    brand = s.str.extract(r"^([A-Z]+)")[0]

    # -----------------------------------
    # 3. EXUN 예외 처리
    # -----------------------------------
    mask_exun = s.str.startswith("EXUN")

    brand = brand.where(~mask_exun, "EX")
    dch.loc[mask_exun, "등급"] = "UN"

    # -----------------------------------
    # 4. 브랜드 저장
    # -----------------------------------
    dch["브랜드"] = brand

    # -----------------------------------
    # 5. 평균중량 (유지)
    # -----------------------------------
    w = (
        dch["규격단위중량"]
        .fillna("")
        .astype(str)
        .str.replace(r"\(.*?\)", "", regex=True)
    )

    dch["평균중량"] = (
        w.str.extract(r"(\d+(?:\.\d+)?)")[0]
        .astype(float)
    )

    # -----------------------------------
    # 6. 기본 등급 (나머지)
    # -----------------------------------
    if "등급" not in dch.columns:
        dch["등급"] = None

    return dch


# =========================================================
# 한라 곤지암 / 동탄
# =========================================================
def hl_eda(data1):

    if data1 is None or data1.empty:
        return data1

    # drop_duplicates() 금지: 같은 상품이 수량만 다른 두 로트로 잡혀도 여기서
    # 한쪽이 지워지면 박스 수가 손실된다. 중복 로트 합산은 list_eda()의
    # azy_data 단계(groupby+재고수량 합산)에서 처리한다.
    hl = data1.copy()

    # =================================================
    # 평균중량 = 원본 중량열(소수점 2자리) ÷ 재고수량 (2026-08-11, 규격단위중량
    # 파싱 방식 대신 실측 중량 기준으로 변경)
    # =================================================
    _weight = pd.to_numeric(
        hl["중량"].astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    ).round(2)
    _qty = pd.to_numeric(
        hl["재고수량"].astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    )
    hl["평균중량"] = (_weight / _qty).round(2)

    # =================================================
    # 기타정보
    # =================================================
    s = hl["기타정보"].astype(str)

    # 앞 괄호 제거
    s = s.str.replace(
        r"^\(.*?\)",
        "",
        regex=True
    )

    # =================================================
    # / 기준 분리
    # =================================================
    tmp = s.str.split(
        "/",
        n=2,
        expand=True
    )

    tmp = tmp.reindex(columns=[0, 1, 2])

    hl["등급"] = tmp[0]
    hl["ESTNO"] = tmp[1]
    hl["브랜드"] = tmp[2]

    # =================================================
    # 정리
    # =================================================
    for col in ["등급", "ESTNO", "브랜드"]:

        hl[col] = (
            hl[col]
            .fillna("")
            .astype(str)
            .str.replace(
                r"\(.*?\)",
                "",
                regex=True
            )
            # 브랜드 뒤에 "_순번" 형태 접미사가 붙는 경우 제거 (예: PERDIGAO_1046867 -> PERDIGAO)
            .str.replace(
                r"_\d+$",
                "",
                regex=True
            )
            .str.strip()
        )

    # =================================================
    # 브랜드만 있는 경우
    # =================================================
    mask = ~s.str.contains("/")

    hl.loc[mask, "브랜드"] = (
        s[mask]
        .str.replace(
            r"\d+\.?\d*$",
            "",
            regex=True
        )
        .str.strip()
    )

    hl.loc[
        mask,
        ["등급", "ESTNO"]
    ] = None

    hl = hl.drop(
        columns=["기타정보"],
        errors="ignore"
    )

    return hl


# =========================================================
# 전체 통합
# =========================================================
def else_df_eda(
    kd,
    ki,
    sjn,
    dch,
    hlk,
    hld
):

    # 강동
    kd = kd_eda(kd)

    # 경인 / 삼진
    ki = ki_eda(ki)
    sjn = sjn_eda(sjn)

    # 대청
    dch = dch_eda(dch)

    # 한라
    hlk = hl_eda(hlk)
    hld = hl_eda(hld)

    # =====================================================
    # 병합
    # =====================================================
    dfs = [kd, ki, sjn, dch, hlk, hld]
    valid_dfs = [
        d for d in dfs
        if d is not None and not d.empty
    ]

    df = pd.concat(
        valid_dfs,
        ignore_index=True
    )

    # 공통 전처리(eda_standard)는 list_eda()가 전체 azy_data를 합친 뒤 한 번만 호출한다.
    # 여기서 먼저 돌리면 파손/상이품/반품 등 한정어가 상품명에서 미리 잘려나가고,
    # list_eda()의 두 번째 eda_standard() 호출이 _auto_상태/_auto_메모를 빈 값으로
    # 리셋한 뒤 재탐지를 시도해도 이미 문자열이 없어 매칭에 실패 — 특이품 태깅이 통째로 날아간다.

    # =====================================================
    # 불필요 컬럼 제거
    # =====================================================
    df = df.drop(
        columns=["규격단위중량", "기타정보"],
        errors="ignore"
    )

    return df