
import pandas as pd


def equal_df(new):
    # 기존 재고장
    old = pd.read_excel(
        "back_end/data/[창고]재고장(전미림).xlsx",
        sheet_name="재고장"
    )

    # 곤지암만
    old = old[
        old["창고"]
        .astype(str)
        .str.strip()
        .str.startswith("곤")
    ]

    # 첫 번째 열 제거
    old = old.iloc[:, 1:]

    # 필요한 컬럼만 선택
    old = old[
        ["품목", "브랜드", "등급", "EST", "현재고", "BL", "창고", "유통기한", "평중"]
    ]

    # 컬럼명 변경
    old.columns = [
        "수탁품",
        "브랜드",
        "등급",
        "ESTNO",
        "재고수량",
        "BL번호",
        "창고",
        "유통기한",
        "평균중량"
    ]

    # ------------------
    # 데이터 정리
    # ------------------

    for df in [old, new]:

        df["유통기한"] = (
            pd.to_datetime(
                df["유통기한"],
                errors="coerce"
            )
            .dt.strftime("%Y-%m-%d")
        )

        df["재고수량"] = (
            pd.to_numeric(
                df["재고수량"],
                errors="coerce"
            )
            .astype("Int64")
        )

        df["BL번호"] = (
            df["BL번호"]
            .astype(str)
            .str.replace("*", "", regex=False)
            .str.replace("\\", "", regex=False)
            .str.strip()
        )

        df["ESTNO"] = (
            df["ESTNO"]
            .astype(str)
            .str.strip()
        )

        df["창고"] = (
            df["창고"]
            .astype(str)
            .str.strip()
        )

        df["수탁품"] = (
            df["수탁품"]
            .astype(str)
            .str.strip()
        )

    # ------------------
    # 비교
    # ------------------

    key_cols = ["BL번호", "수탁품", "창고"]

    result = old.merge(
        new,
        on=key_cols,
        how="outer",
        suffixes=("_old", "_new"),
        indicator=True
    )

    result["상이"] = ""

    # 삭제
    result.loc[
        result["_merge"] == "left_only",
        "상이"
    ] = "deleted"

    # 신규
    result.loc[
        result["_merge"] == "right_only",
        "상이"
    ] = "new"

    # 재고수량 변경
    result.loc[
        (result["_merge"] == "both")
        &
        (
            pd.to_numeric(result["재고수량_old"], errors="coerce")
            !=
            pd.to_numeric(result["재고수량_new"], errors="coerce")
        ),
        "상이"
    ] = "!"

    # ------------------
    # new 형식으로 컬럼 복원
    # ------------------

    result["브랜드"] = result["브랜드_new"].fillna(result["브랜드_old"])
    result["등급"] = result["등급_new"].fillna(result["등급_old"])
    result["ESTNO"] = result["ESTNO_new"].fillna(result["ESTNO_old"])
    result["재고수량"] = result["재고수량_new"].fillna(result["재고수량_old"])
    result["유통기한"] = result["유통기한_new"].fillna(result["유통기한_old"])
    result["평균중량"] = result["평균중량_new"].fillna(result["평균중량_old"])

    final = result[
        [
            "수탁품",
            "브랜드",
            "등급",
            "ESTNO",
            "재고수량",
            "BL번호",
            "창고",
            "유통기한",
            "평균중량",
            "상이"
        ]
    ].copy()

    # 보기 좋게 정렬
    final = final.sort_values(
        ["상이", "수탁품", "BL번호"],
        na_position="last"
    ).reset_index(drop=True)

    return final