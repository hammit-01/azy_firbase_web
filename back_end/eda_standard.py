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

    df.loc[df["브랜드"] == "EXCELCH", "등급"] = "CH"
    df.loc[df["브랜드"] == "EXCELCH", "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELSEL", "등급"] = "SEL"
    df.loc[df["브랜드"] == "EXCELSEL", "브랜드"] = "EXCEL"
    df.loc[df["브랜드"] == "EXCELPRI", "등급"] = "PRI"
    df.loc[df["브랜드"] == "EXCELPRI", "브랜드"] = "EXCEL"

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