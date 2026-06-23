def eda_standard(df):
    # 계육
    df.loc[
        df["수탁품"] == "닭장각정육",
        "평균중량"
    ] = 12
    df.loc[
        df["수탁품"] == "닭장각정육(파손)",
        "평균중량"
    ] = 12
    df.loc[
        (df["브랜드"] == "TEYS") &
        (df["수탁품"] == "곱창"),
        "평균중량"
    ] = 15
    df.loc[
        (df["브랜드"] == "TEYS") &
        (df["수탁품"] == "깐양"),
        "평균중량"
    ] = 20
    df.loc[
        (df["브랜드"] == "국내산") &
        (df["수탁품"] == "닭가슴살"),
        "평균중량"
    ] = 20
    df.loc[
        (df["브랜드"] == "AURORA") &
        (df["수탁품"] == "닭장각"),
        "평균중량"
    ] = 15
    df.loc[
        (df["브랜드"] == "SEARA") &
        (df["수탁품"] == "닭장각"),
        "평균중량"
    ] = 15

    df.loc[
        (df["브랜드"] == "ACC") &
        (df["수탁품"] == "대창"),
        "평균중량"
    ] = 20
    df.loc[
        (df["브랜드"] == "ROSDERRA") &
        (df["수탁품"] == "돈갈매기"),
        "평균중량"
    ] = 10
    df.loc[
        (df["브랜드"] == "LOCKS") &
        (df["수탁품"] == "돈단족"),
        "평균중량"
    ] = 10
    df.loc[
        (df["브랜드"] == "SEARA") &
        (df["수탁품"] == "돈단족"),
        "평균중량"
    ] = 18

    df.loc[
        (df["브랜드"] == "SEARA") &
        (df["수탁품"] == "돈목뼈"),
        "평균중량"
    ] = 15
    df.loc[
        (df["브랜드"] == "SWIFT") &
        (df["수탁품"] == "돈목뼈"),
        "평균중량"
    ] = 15.88
    df.loc[
        (df["브랜드"] == "TONNIES") &
        (df["수탁품"] == "돈목뼈"),
        "평균중량"
    ] = 13
    df.loc[
        (df["수탁품"] == "새우"),
        "평균중량"
    ] = 9
    df.loc[
        (df["브랜드"] == "EXCEL") &
        (df["수탁품"] == "우건"),
        "평균중량"
    ] = 6.8
    df.loc[
        (df["브랜드"] == "EXCEL") &
        (df["수탁품"] == "홍창"),
        "평균중량"
    ] = 6.8
    df.loc[
        (df["브랜드"] == "SWIFT") &
        (df["수탁품"] == "홍창"),
        "평균중량"
    ] = 9.98
    df.loc[
        (df["브랜드"] == "COPACAL") &
        (df["수탁품"] == "통날개"),
        "평균중량"
    ] = 15
    df.loc[
        (df["브랜드"] == "KEKEN") &
        (df["수탁품"] == "항정살"),
        "평균중량"
    ] = 10
    df.loc[
        (df["브랜드"] == "국내산") &
        (df["수탁품"] == "작업돈껍데기"),
        "평균중량"
    ] = 15
    df.loc[
        (df["브랜드"] == "INCARLOPSA") &
        (df["수탁품"] == "돈목살"),
        "평균중량"
    ] = 15

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
        (df["수탁품"] == "삼겹양지")&
        (df["등급"] == ""),
        "등급"
    ] = "UN"
    df.loc[
        (df["브랜드"] == "SWIFT") &
        (df["수탁품"] == "삼겹양지파손")&
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

    df["등급"] = (df["등급"].astype(str).str.replace("#", "", regex=False))

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

    # =================================================
    # 새우
    # =================================================
    shrimp_mask = product.str.contains("새우", na=False)

    df.loc[shrimp_mask, "수탁품"] = "생칵테일새우"
    df.loc[shrimp_mask, "등급"] = "9KG"

    # =================================================
    # 인도
    # =================================================
    india_mask = (
        shrimp_mask
        & product.str.contains("인도", na=False)
    )

    df.loc[india_mask, "ESTNO"] = "인도"

    df.loc[
        india_mask
        & product.str.contains("26/30", na=False),
        "브랜드"
    ] = "26/30"

    df.loc[
        india_mask
        & product.str.contains("31/40", na=False),
        "브랜드"
    ] = "31/40"

    # =================================================
    # 페루
    # =================================================
    peru_mask = (
        shrimp_mask
        & product.str.contains("페루", na=False)
    )

    df.loc[peru_mask, "ESTNO"] = "페루"

    df.loc[
        peru_mask
        & product.str.contains("41/50", na=False),
        "브랜드"
    ] = "41/50"

    df.loc[
        peru_mask
        & product.str.contains("31/40", na=False),
        "브랜드"
    ] = "31/40"

    df.loc[df["브랜드"] == "EXCELCH", "등급"] = "CH"
    df.loc[df["브랜드"] == "EXCELCH", "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELSEL", "등급"] = "SEL"
    df.loc[df["브랜드"] == "EXCELSEL", "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELPRI", "등급"] = "PRI"
    df.loc[df["브랜드"] == "EXCELPRI", "브랜드"] = "EXCEL"

    mask = df["등급"] == "CH-ANGUS"
    df.loc[mask, "등급"] = "3P"
    df.loc[mask, "ESTNO"] = "3D"

    mask = df["등급"] == "S-GF"
    df.loc[mask, "등급"] = "GF"
    df.loc[mask, "ESTNO"] = "640"

    mask = df["수탁품"] == "우척BBQ빽립A"
    df.loc[mask, "등급"] = "A"

    df.loc[
        df["수탁품"].astype(str).str.contains("PERDI", case=False, na=False),
        "브랜드"
    ] = "PERDIGAO"
    df.loc[
        df["수탁품"].astype(str).str.contains("SADIA", case=False, na=False),
        "브랜드"
    ] = "SADIA"
    df.loc[
        df["수탁품"].astype(str).str.contains("SEARA", case=False, na=False),
        "브랜드"
    ] = "SEARA"

    # df.loc[
    #     df["규격단위중량"].astype(str).str.contains("PERDI", case=False, na=False),
    #     "브랜드"
    # ] = "PERDIGAO"
    # df.loc[
    #     df["규격단위중량"].astype(str).str.contains("SADIA", case=False, na=False),
    #     "브랜드"
    # ] = "SADIA"
    # df.loc[
    #     df["규격단위중량"].astype(str).str.contains("SEARA", case=False, na=False),
    #     "브랜드"
    # ] = "SEARA"
    return df