import numpy as np

def kd_eda(df):
    # 등급, est
    df["등급"] = df["기타정보"].str.extract(r"^([^/]+)")
    # /로 시작하는 경우 (등급 없음)
    df.loc[df["기타정보"].str.startswith("/"), "등급"] = None
    df["기타정보"] = df["기타정보"].astype(str).str.replace("/", "", regex=False)

    # 브랜ㄷ, 중량
    df[["브랜드", "평균중량"]] = df["규격단위중량"].astype(str).str.extract(
        r"([A-Za-z]+)(\d+\.?\d*\s*[A-Za-z]+)"
    )

    df = df.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    return df

# 경인, 삼진1, 삼진2
def ki_eda(ki, sjn):
    dfs = {"ki": ki, "sjn": sjn}
    for name, d in dfs.items():  # ✅ 수정
        s = d["기타정보"].astype(str)

        # 1. 등급 (괄호 앞)
        d["등급"] = s.str.extract(r"^([^(/]+)")
        d.loc[s.str.startswith("("), "등급"] = None

        # 2. 브랜드 (괄호 안)
        d["브랜드"] = s.str.extract(r"\((.*?)\)")

        # 3. ESTNO (맨 뒤)
        d["ESTNO"] = s.str.extract(r"(\d+[A-Za-z]*)$")

        # 4. 평균중량
        d["평균중량"] = d["규격단위중량"].astype(str).str.extract(r"(\d+\.?\d*KG)")

    ki = ki.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    sjn = sjn.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    return ki, sjn

# 대청, 한라곤지암, 한라동탄
def eda(dch, hlk, hld):
    # 중량 같이, 브랜드/est/등급 따로
    #중량
    dfs = {"dch": dch, "hlk": hlk, "hld": hld}
    
    for name, d in dfs.items():
        if name == "hlk" or name == "dch":
            d["평균중량"] = d["규격단위중량"].astype(str).str.extract(r"(\d+\.?\d*KG)")
            if name == "dch":
                # 브랜드 지정
                conditions = [
                    d["기타정보"].str.contains("TEYS", na=False),
                    d["기타정보"].str.contains("SADIA", na=False),
                    d["기타정보"].str.contains("SWIFT", na=False),
                    d["기타정보"].str.contains(r"\bEX\b", na=False),
                    d["기타정보"].str.contains("SEARA", na=False),
                    d["기타정보"].str.contains("TONNIES", na=False),
                ]

                choices = ["TEYS", "SADIA", "SWIFT", "EXCEL", "SEARA", "TONNIES"]

                d["브랜드"] = np.select(conditions, choices, default=None)

                # 브랜드 이후 값
                s = d["기타정보"].str.extract(
                    r"\b(TEYS|SADIA|SWIFT|SEARA|TONNIES|EX)\b(.*)"
                )[1]

                # SADIA / SEARA
                mask = d["브랜드"].isin(["SADIA", "SEARA"])
                d.loc[mask, "ESTNO"] = s[mask]

                # 나머지
                not_mask = ~mask
                d.loc[not_mask, "등급"] = s[not_mask].str.extract(r"([A-Za-z/]+)(?=\d)")
                d.loc[not_mask, "ESTNO"] = s[not_mask].str.extract(r"(\d+[A-Za-z]*)")

            else:
                s = d["기타정보"].astype(str)

                # 1. 앞쪽 괄호 제거
                s = s.str.replace(r"^\(.*?\)", "", regex=True)

                # 2. split (최대 3개만)
                tmp = s.str.split("/", n=2, expand=True)

                # 3. 컬럼 매핑 (없으면 자동 NaN)
                d["등급"] = tmp[0]
                d["ESTNO"] = tmp[1]
                d["브랜드"] = tmp[2]

                # 4. 괄호 제거 + 정리
                d["등급"] = d["등급"].str.replace(r"\(.*?\)", "", regex=True).str.strip()
                d["브랜드"] = d["브랜드"].str.strip()
                d["ESTNO"] = d["ESTNO"].str.strip()

                # 5. 브랜드만 있는 케이스 처리
                mask = ~s.str.contains("/")
                d.loc[mask, "브랜드"] = s[mask]
                d.loc[mask, ["등급", "ESTNO"]] = None


        elif name == "hld":
            s = d["규격단위중량"].astype(str)
            # 1. 평균중량 (공통: KG 추출)
            d["평균중량"] = s.str.extract(r"(\d+\.?\d*KG)")
            # 2. 브랜드 (박스: 있는 경우만)
            d["브랜드"] = s.str.extract(r"박스:([A-Za-z]+)")
            # 3. 공백 정리
            d["브랜드"] = d["브랜드"].str.strip()
            
    
    dch = dch.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    hlk = hlk.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    hld = hld.drop(columns=["규격단위중량", "기타정보"], errors="ignore")
    
    return dch, hlk, hld


def else_df_eda(df):
    df["규격단위중량"] = df["규격단위중량"].str.replace("@@", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("#", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("_", "", regex=False)
    df["수탁품"] = df["수탁품"].str.replace("-", "", regex=False)
    
    # BL / 이력번호
    s = df["B/L NO식별번호"].astype(str)
    # 길이 조건
    mask = s.str.len() > 20
    # 1. 이력번호 (뒤 12자리)
    df.loc[mask, "이력번호"] = s.str[-12:]
    # 2. BL번호 (앞부분)
    df.loc[mask, "BL번호"] = s.str[:-12]
    # 3. 20자 이하 → 전부 BL번호
    df.loc[~mask, "BL번호"] = s
    df.loc[~mask, "이력번호"] = None
    df = df.drop(columns=["B/L NO식별번호"], errors="ignore")

    # 소비기한제조일자
    s = df["소비기한제조일자"].astype(str)
    # 날짜 분리
    df[["유통기한", "제조일자"]] = s.str.extract(
        r"(\d{4}\.\d{2}\.\d{2})\D*(\d{4}\.\d{2}\.\d{2})?"
    )
    df = df.drop(columns=["소비기한제조일자"], errors="ignore")
    
    # 수탁품 전처리
    df["수탁품"] = (
        df["수탁품"]
        .astype(str)
        .str.replace(r"^\(.*?\)\s*", "", regex=True)
        .str.replace(r"^[^\w가-힣]+", "", regex=True)
        .str.strip()
    )

    # 기타정보 분리
    df["기타정보"] = df["수탁품"].str.replace(r"[가-힣\s]", "", regex=True)
    df["수탁품"] = df["수탁품"].str.replace(r"[^가-힣\s]", "", regex=True).str.strip()




    # 창고별 분리
    kd = df[df["창고"].isin(["강동1", "강동2"])].copy()
    kd = kd_eda(kd)

    ki = df[df["창고"] == "경인"].copy()
    sjn = df[df["창고"].isin(["삼진1", "삼진2"])].copy()
    ki, sjn = ki_eda(ki, sjn)
    
    dch = df[df["창고"] == "대청"].copy()
    hlk = df[df["창고"] == "한라"].copy()
    hld = df[df["창고"] == "한라동탄"].copy()
    dch, hlk, hld = eda(dch, hlk, hld)
        
    kd = kd.drop_duplicates()
    ki = ki.drop_duplicates()
    sjn = sjn.drop_duplicates()
    dch = dch.drop_duplicates()
    hlk = hlk.drop_duplicates()
    hld = hld.drop_duplicates()

    return kd,ki,sjn,dch,hlk,hld
