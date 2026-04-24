import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from zoneinfo import ZoneInfo

def to_date(x):
    if pd.isna(x):
        return ""

    try:
        # 숫자형 엑셀 날짜 (46758.0)
        if isinstance(x, (int, float)):
            return (
                pd.to_datetime("1899-12-30") +
                pd.to_timedelta(int(x), unit="D")
            ).strftime("%Y-%m-%d")

        x = str(x).strip()

        # 문자열 숫자 46758.0
        if x.replace(".", "", 1).isdigit():
            num = int(float(x))
            return (
                pd.to_datetime("1899-12-30") +
                pd.to_timedelta(num, unit="D")
            ).strftime("%Y-%m-%d")

        # 20260415 형태
        if x.isdigit() and len(x) == 8:
            return pd.to_datetime(x, format="%Y%m%d").strftime("%Y-%m-%d")

        # 일반 날짜 문자열
        return pd.to_datetime(x).strftime("%Y-%m-%d")

    except:
        return ""



def to_int(x):
    try:
        if pd.isna(x):
            return 0
        return int(str(x).replace(",", "").strip())
    except:
        return 0

def post():
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    # Firebase 초기화
    cred = credentials.Certificate("azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # 엑셀 읽기
    # df = pd.read_excel("back_end/jns.xlsx")
    df = pd.read_excel(
        "back_end/data/[창고]재고장(전미림).xlsx",
        sheet_name="재고장"
    )

    xls = pd.ExcelFile("back_end/data/[창고]재고장(전미림).xlsx")
    print(xls.sheet_names)

    print(df.head())

    # 업로드
    for _, row in df.iterrows():
        doc_ref = db.collection("all_data").document()

        doc_ref.set({
            "상품명": str(row.get("수탁품", "")).strip(),
            "브랜드": str(row.get("브랜드", "")).strip(),
            "등급": str(row.get("등급", "")).strip(),
            "ESTNO": str(row.get("ESTNO", "")).strip(),
            "재고수량": to_int(row.get("재고수량")),
            "BL번호": str(row.get("BL번호", "")).strip(),

            "창고": str(row.get("창고", "")).strip(),
            "유통기한": to_date(row.get("유통기한")),
            "중량": True if pd.notna(row.get("중량")) else None,
            "평균중량": str(row.get("평균중량", "")).strip(),
            "출고예정일": str(row.get("출고예정일")),
            "홀딩": str(row.get("홀딩")),

            "이력번호": True if pd.notna(row.get("이력번호")) else None,
            "가공일자": True if pd.notna(row.get("소비기한")) else None,
            "수집일": str(today),
            "동결": True if pd.notna(row.get("동결")) else None,
            "사용불가": True if pd.notna(row.get("사용불가")) else None
        })


    print("🔥 업로드 완료")

post()