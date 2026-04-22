import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

def to_date(x):
    if pd.isna(x):
        return ""

    x = str(x).strip()

    try:
        # 20260415 형태
        if x.isdigit() and len(x) == 8:
            return pd.to_datetime(x, format="%Y%m%d").strftime("%Y-%m-%d")

        # 2028.09.25 형태
        return pd.to_datetime(x).strftime("%Y-%m-%d")

    except:
        return x


def to_int(x):
    try:
        if pd.isna(x):
            return 0
        return int(str(x).replace(",", "").strip())
    except:
        return 0

def post():
    # Firebase 초기화
    cred = credentials.Certificate("azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json")
    firebase_admin.initialize_app(cred)

    db = firestore.client()

    # 엑셀 읽기
    df = pd.read_excel("back_end/jns.xlsx")

    print(df.head())

    # 업로드
    for _, row in df.iterrows():
        doc_ref = db.collection("all_data").document()

        doc_ref.set({
            "상품명": str(row.get("수탁품", "")),
            "브랜드": str(row.get("브랜드", "")),
            "등급": str(row.get("등급", "")),
            "ESTNO": str(row.get("ESTNO", "")),
            "평균중량": str(row.get("평균중량", "")),
            "BL번호": str(row.get("BL번호", "")),
            "이력번호": str(row.get("이력번호", "")),
            "재고수량": to_int(row.get("재고수량")),
            "중량": str(row.get("중량", "")),
            "창고": str(row.get("창고", "")),
            "유통기한": to_date(row.get("유통기한")),
            "소비기한": to_date(row.get("소비기한")),
            "수집일": to_date(row.get("수집일")),
        })

    print("🔥 업로드 완료")

post()