
# import gspread
import pandas as pd

# SPREADSHEET_ID = "1bHW-lQTHDfgNOPzSw2qIoQQ5yg2bDgb8qNqNxyDPvvk"
# SERVICE_ACCOUNT_JSON = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"


def equal_df(new, old):
    new = new.copy()
    old = old.copy()

    # # 기존 재고장 — 구글 시트에서 로드
    # gc = gspread.service_account(filename=SERVICE_ACCOUNT_JSON)
    # ws = gc.open_by_key(SPREADSHEET_ID).worksheet("재고장")
    # old = pd.DataFrame(ws.get_all_records())

    # # 곤지암만
    # old = old[
    #     old["창고"]
    #     .astype(str)
    #     .str.strip()
    #     .str.startswith("곤")
    # ]

    # # 필요한 컬럼만 선택 및 컬럼명 변경
    # old = old[
    #     ["품목", "브랜드", "등급", "EST", "현재고", "BL", "창고", "유통기한", "평중"]
    # ]
    # old.columns = [
    #     "수탁품",
    #     "브랜드",
    #     "등급",
    #     "ESTNO",
    #     "재고수량",
    #     "BL번호",
    #     "창고",
    #     "유통기한",
    #     "평균중량"
    # ]

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
                df["재고수량"].astype(str).str.replace(",", "", regex=False),
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

    # 생칵테일새우 BL번호에서 '-' 이후 제거 (old/new 동일 적용)
    for df in [old, new]:
        mask = df["수탁품"].str.contains("생칵테일새우", na=False)
        df.loc[mask, "BL번호"] = df.loc[mask, "BL번호"].str.split("-").str[0]

    old = old.drop_duplicates()

    # 유통기한 연-월 비교키 추가 (old는 정확한 날짜, new는 월초 날짜로 기재돼 오차 흡수)
    for df in [old, new]:
        df["유통기한_ym"] = (
            pd.to_datetime(df["유통기한"], errors="coerce")
            .dt.strftime("%Y-%m")
        )

    # ------------------
    # 비교
    # ------------------

    key_cols = ["재고수량", "BL번호", "창고", "유통기한_ym", "수탁품"]

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

    # ------------------
    # new 형식으로 컬럼 복원
    # key_cols는 suffix 없음, 유통기한은 별도 복원
    # ------------------

    result["유통기한"] = result["유통기한_new"].fillna(result["유통기한_old"])
    result["브랜드"] = result["브랜드_new"].fillna(result["브랜드_old"])
    result["등급"] = result["등급_new"].fillna(result["등급_old"])
    result["ESTNO"] = result["ESTNO_new"].fillna(result["ESTNO_old"])
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
    ].drop_duplicates().copy()

    # ------------------
    # 재고 변동 감지: deleted+new 1:1 쌍 → ▲/▼ 표시 후 deleted 제거
    # ------------------
    pair_key = ["수탁품", "BL번호", "창고"]

    del_df = final[final["상이"] == "deleted"][pair_key + ["유통기한", "재고수량"]].copy()
    new_df = final[final["상이"] == "new"][pair_key + ["유통기한", "재고수량"]].copy()

    for d in [del_df, new_df]:
        d["_ym"] = pd.to_datetime(d["유통기한"], errors="coerce").dt.strftime("%Y-%m")

    ym_key = pair_key + ["_ym"]
    pairs = del_df.merge(new_df, on=ym_key, suffixes=("_old", "_new"), how="inner")

    # 1:1 쌍만 처리
    del_cnt = del_df.groupby(ym_key).size().rename("del_cnt")
    new_cnt = new_df.groupby(ym_key).size().rename("new_cnt")
    pairs = (
        pairs
        .join(del_cnt, on=ym_key)
        .join(new_cnt, on=ym_key)
    )
    pairs = pairs[(pairs["del_cnt"] == 1) & (pairs["new_cnt"] == 1)]

    del_idx_to_drop = []
    for _, row in pairs.iterrows():
        old_qty = row["재고수량_old"]
        new_qty = row["재고수량_new"]
        if pd.isna(old_qty) or pd.isna(new_qty):
            continue
        delta = int(new_qty) - int(old_qty)
        delta_str = f"{'▲' if delta > 0 else '▼'}{abs(delta)}"

        new_mask = (
            (final["상이"] == "new") &
            (final["수탁품"] == row["수탁품"]) &
            (final["BL번호"] == row["BL번호"]) &
            (final["창고"] == row["창고"]) &
            (final["재고수량"] == new_qty)
        )
        final.loc[new_mask, "상이"] = delta_str

        del_mask = (
            (final["상이"] == "deleted") &
            (final["수탁품"] == row["수탁품"]) &
            (final["BL번호"] == row["BL번호"]) &
            (final["창고"] == row["창고"]) &
            (final["재고수량"] == old_qty)
        )
        del_idx_to_drop.extend(final[del_mask].index.tolist())

    if del_idx_to_drop:
        final = final.drop(index=del_idx_to_drop)

    # 보기 좋게 정렬
    final = final.sort_values(
        ["상이", "수탁품", "BL번호"],
        na_position="last"
    ).reset_index(drop=True)

    return final