import pandas as pd
from datetime import date


def eda_standard(df):
    # ── 등급 정규화 ───────────────────────────────────────────────────
    df.loc[
        (df["브랜드"] == "EXCEL") &
        (df["수탁품"] == "조각삼겹양지"),
        "등급"
    ] = "UN"
    df.loc[
        (df["브랜드"] == "IBP") &
        (df["수탁품"] == "돈목전지"),
        "등급"
    ] = "2P"
    df.loc[
        (df["브랜드"] == "EXCEL") &
        (df["수탁품"] == "삼겹양지") &
        (df["등급"] == ""),
        "등급"
    ] = "UN"
    df.loc[
        (df["브랜드"] == "SWIFT") &
        (df["수탁품"] == "삼겹양지파손") &
        (df["등급"] == ""),
        "등급"
    ] = "UN"
    df.loc[
        (df["브랜드"] == "TEYS") &
        (df["등급"] == ""),
        "등급"
    ] = "S"
    df.loc[
        (df["브랜드"] == "TEYS") &
        (df["등급"] == "UN"),
        "등급"
    ] = "S"

    df["등급"] = df["등급"].astype(str).str.replace("#", "", regex=False)

    # 수산물 브랜드: 수탁품의 "31-40/9KG" 형식에서 "31/40"을 브랜드로 추출
    sunsanmul_mask = df["브랜드"].astype(str).str.strip() == "수산물"
    if sunsanmul_mask.any():
        extracted = (
            df.loc[sunsanmul_mask, "수탁품"]
            .astype(str)
            .str.extract(r"(\d+)-(\d+)")
        )
        valid = extracted[0].notna()
        df.loc[sunsanmul_mask & valid, "브랜드"] = (
            extracted.loc[valid, 0] + "/" + extracted.loc[valid, 1]
        )

    product = df["수탁품"].astype(str)

    # 새우
    shrimp_mask = product.str.contains("새우", na=False)
    df.loc[shrimp_mask, "수탁품"] = "생칵테일새우"
    df.loc[shrimp_mask, "등급"]   = "9KG"

    # 인도
    india_mask = shrimp_mask & product.str.contains("인도", na=False)
    df.loc[india_mask, "ESTNO"] = "인도"
    df.loc[india_mask & product.str.contains("26/30", na=False), "브랜드"] = "26/30"
    df.loc[india_mask & product.str.contains("31/40", na=False), "브랜드"] = "31/40"

    # 페루
    peru_mask = shrimp_mask & product.str.contains("페루", na=False)
    df.loc[peru_mask, "ESTNO"] = "페루"
    df.loc[peru_mask & product.str.contains("41/50", na=False), "브랜드"] = "41/50"
    df.loc[peru_mask & product.str.contains("31/40", na=False), "브랜드"] = "31/40"

    # 수탁품에 "냉장" 포함 시 앞으로 이동 (예: "부채살(냉장)" → "냉장부채살")
    냉장_mask = (
        df["수탁품"].astype(str).str.contains("냉장", na=False)
        & ~df["수탁품"].astype(str).str.startswith("냉장")
    )
    df.loc[냉장_mask, "수탁품"] = (
        "냉장"
        + df.loc[냉장_mask, "수탁품"]
        .astype(str)
        .str.replace(r"\s*[\(\[]냉장[\)\]]", "", regex=True)
        .str.replace("냉장", "", regex=False)
        .str.strip()
    )

    # 등급에 "냉동" 포함 시 제거
    df["등급"] = (
        df["등급"].astype(str)
        .str.replace("냉동", "", regex=False)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )

    # ESTNO "PDTO" 제거
    df["ESTNO"] = (
        df["ESTNO"].astype(str)
        .str.replace("PDTO", "", regex=False)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )

    # 브랜드 정규화
    df.loc[df["브랜드"] == "EXCELCH",  "등급"]   = "CH"
    df.loc[df["브랜드"] == "EXCELCH",  "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELSEL", "등급"]   = "SEL"
    df.loc[df["브랜드"] == "EXCELSEL", "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELPRI", "등급"]   = "PRI"
    df.loc[df["브랜드"] == "EXCELPRI", "브랜드"] = "EXCEL"

    mask = df["등급"] == "CH-ANGUS"
    df.loc[mask, "등급"]  = "3P"
    df.loc[mask, "ESTNO"] = "3D"

    mask = df["등급"] == "S-GF"
    df.loc[mask, "등급"]  = "GF"
    df.loc[mask, "ESTNO"] = "640"

    mask = df["수탁품"] == "우척BBQ빽립A"
    df.loc[mask, "등급"] = "A"

    # 소갈비/SWIFT/ESTNO=3D는 원본 WMS에 등급 정보가 아예 없어 사용자 확인으로 고정값 지정
    mask = (df["브랜드"] == "SWIFT") & (df["수탁품"] == "소갈비") & (df["ESTNO"] == "3D")
    df.loc[mask, "등급"] = "UN"

    df.loc[df["수탁품"].astype(str).str.contains("PERDI", case=False, na=False), "브랜드"] = "PERDIGAO"
    df.loc[df["수탁품"].astype(str).str.contains("SADIA", case=False, na=False), "브랜드"] = "SADIA"
    df.loc[df["수탁품"].astype(str).str.contains("SEARA", case=False, na=False), "브랜드"] = "SEARA"

    # ── 평균중량: EDA 추출값 유지, 알려진 규격 상품만 고정값으로 덮어씌움 ──
    if "평균중량" not in df.columns:
        df["평균중량"] = None
    df["평균중량"] = pd.to_numeric(df["평균중량"], errors="coerce")

    # 우육
    df.loc[(df["브랜드"] == "TEYS")  & (df["수탁품"] == "곱창"),     "평균중량"] = 15.0
    df.loc[(df["브랜드"] == "OAKEY") & (df["수탁품"] == "안창살"),   "평균중량"] = 15.0
    df.loc[(df["브랜드"] == "OAKEY") & (df["수탁품"] == "늑간살"),   "평균중량"] = 15.0
    df.loc[(df["브랜드"] == "EXCEL") & (df["수탁품"] == "우건"),     "평균중량"] = 6.8
    df.loc[(df["브랜드"] == "SWIFT") & (df["수탁품"] == "우건"),     "평균중량"] = 9.98
    df.loc[(df["브랜드"] == "SWIFT") & (df["수탁품"] == "우건(뒤)"), "평균중량"] = 20.0
    df.loc[(df["브랜드"] == "TEYS")  & (df["수탁품"] == "우건"),     "평균중량"] = 27.2
    df.loc[(df["브랜드"] == "TEYS")  & (df["수탁품"] == "우건(뒤)"), "평균중량"] = 27.2
    df.loc[(df["브랜드"] == "EXCEL") & (df["수탁품"] == "홍창"),     "평균중량"] = 6.8
    df.loc[(df["브랜드"] == "SWIFT") & (df["수탁품"] == "홍창"),     "평균중량"] = 9.98

    # TEYS 깐양: 등급에서 KG 수치 추출 (예: "20KG" → 20.0, "27.2KG" → 27.2)
    teys_kang_mask = (df["브랜드"] == "TEYS") & (df["수탁품"] == "깐양")
    if teys_kang_mask.any():
        kg_extracted = (
            df.loc[teys_kang_mask, "등급"]
            .astype(str)
            .str.extract(r"(\d+\.?\d*)")
        )
        df.loc[teys_kang_mask, "평균중량"] = pd.to_numeric(kg_extracted[0], errors="coerce")

    # 계육 (브라질산: PERDIGAO, SADIA, SEARA)
    brazil_mask = df["브랜드"].isin(["PERDIGAO", "SADIA", "SEARA"])
    df.loc[brazil_mask & (df["수탁품"] == "닭장각"),     "평균중량"] = 15.0
    df.loc[brazil_mask & (df["수탁품"] == "닭장각정육"), "평균중량"] = 12.0
    df.loc[brazil_mask & (df["수탁품"] == "닭가슴살"),   "평균중량"] = 12.0

    # 돈육
    df.loc[(df["브랜드"] == "ROSDERRA") & (df["수탁품"] == "돈갈매기"), "평균중량"] = 10.0
    df.loc[(df["브랜드"] == "LOCKS")    & (df["수탁품"] == "돈단족"),   "평균중량"] = 10.0
    df.loc[(df["브랜드"] == "SEARA")    & (df["수탁품"] == "돈단족"),   "평균중량"] = 18.0
    df.loc[(df["브랜드"] == "SWIFT")    & (df["수탁품"] == "돈목뼈"),   "평균중량"] = 15.88
    df.loc[(df["브랜드"] == "SEARA")    & (df["수탁품"] == "돈목뼈"),   "평균중량"] = 15.0
    df.loc[(df["브랜드"] == "SEABOARD") & (df["수탁품"] == "돈볼살"),   "평균중량"] = 13.6
    df.loc[(df["브랜드"] == "SEARA")    & (df["수탁품"] == "돈갈비"),   "평균중량"] = 15.0

    # TONNIES 돈단족: 유통기한 - 730일이 올해인 제품만 적용
    tonnies_mask = (df["브랜드"] == "TONNIES") & (df["수탁품"] == "돈단족")
    if tonnies_mask.any():
        expire = pd.to_datetime(df["유통기한"], errors="coerce")
        manufactured_year = (expire - pd.Timedelta(days=730)).dt.year
        df.loc[tonnies_mask & (manufactured_year == date.today().year), "평균중량"] = 10.0

    # ── 특이품 자동 감지 (신규 행 생성 시 상태/메모 기본값으로 사용 — _upload_azy 참고) ──
    df["_auto_상태"] = ""
    df["_auto_메모"] = ""

    # 1) 상품명에 파손/상이품/반품 포함 → 상품명에서 제거하고 상태=특이품, 메모=사유
    # "반품입고"처럼 뒤에 "입고"가 붙어 나오는 경우가 많아 같이 제거 (메모는 사유만 저장)
    qualifier_pattern = r"(파손|상이품|반품)"
    extracted = df["수탁품"].astype(str).str.extract(qualifier_pattern)[0]
    has_qualifier = extracted.notna()
    df.loc[has_qualifier, "수탁품"] = (
        df.loc[has_qualifier, "수탁품"]
        .astype(str)
        .str.replace(qualifier_pattern + r"(입고)?", "", regex=True)
        .str.strip()
    )
    df.loc[has_qualifier, "_auto_상태"] = "특이품"
    df.loc[has_qualifier, "_auto_메모"] = extracted[has_qualifier]

    # 2) 상품명/브랜드/등급/ESTNO 중 하나라도 비어있음 → 상태=null (메모는 안 건드림)
    core_cols = ["수탁품", "브랜드", "등급", "ESTNO"]
    missing_mask = pd.Series(False, index=df.index)
    for c in core_cols:
        if c in df.columns:
            missing_mask = missing_mask | df[c].isna() | (df[c].astype(str).str.strip() == "")
    null_only = missing_mask & ~has_qualifier
    df.loc[null_only, "_auto_상태"] = "null"

    return df
