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

def to_float(x):

    if pd.isna(x):
        return ""

    return float(str(x).replace(",", ""))


def to_int(x):
    try:
        if pd.isna(x):
            return 0
        # float("100.0") 후 int 변환 (str→int 직접 변환은 "100.0" 형식에서 실패)
        return int(float(str(x).replace(",", "").strip()))
    except:
        return 0

def to_str(x):

    # NaN 처리
    if pd.isna(x):
        return ""

    # 문자열 변환
    x = str(x).strip()

    # 엑셀 숫자형 .0 제거
    if x.endswith(".0"):
        x = x[:-2]

    return x

def _archive_old_data(db, today):
    """수집일이 오늘이 아닌 all_data 문서를 archive_data로 이동"""
    docs = list(db.collection("all_data").stream())
    to_archive = [
        d for d in docs
        if d.to_dict().get("수집일") and d.to_dict().get("수집일") != today
    ]

    if not to_archive:
        print("아카이브할 이전 데이터 없음")
        return

    archive_ref = db.collection("archive_data")
    BATCH_LIMIT = 250  # 2 ops/doc × 250 = 500 (Firestore batch 한도)

    for i in range(0, len(to_archive), BATCH_LIMIT):
        chunk = to_archive[i:i + BATCH_LIMIT]
        batch = db.batch()
        for doc in chunk:
            batch.set(archive_ref.document(doc.id), doc.to_dict())
            batch.delete(doc.reference)
        batch.commit()

    print(f"이전 데이터 {len(to_archive)}개 archive_data로 이동 완료")


def post(df):
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    # Firebase 초기화
    cred = credentials.Certificate("azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # 이전 날짜 데이터 아카이브
    _archive_old_data(db, today)

    # 오늘 데이터 업로드
    for _, row in df.iterrows():
        bl = to_str(row.get("BL번호", "")).strip()
        weight = to_str(row.get("평균중량", "")).strip()
        weight = weight.replace(".", "") if weight else ""
        expire = to_date(row.get("유통기한"))

        # BL번호 뒤 4자리
        bl_last4 = bl[-4:] if len(bl) >= 4 else bl

        # 날짜를 문자열로 변환 (2026-06-08 -> 20260608)
        expire_str = expire.replace("-", "") if expire else ""

        bl_last4 = bl_last4.replace("/", "_")
        weight = weight.replace("/", "_")
        expire_str = expire_str.replace("/", "_")

        doc_id = f"{bl_last4}_{expire_str}_{weight}"

        doc_ref = db.collection("all_data").document(doc_id)

        doc_ref.set({
            "id": doc_ref.id,
            "pk": doc_id,
            "상품명": to_str(row.get("수탁품", "")).strip(),
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급": to_str(row.get("등급", "")).strip(),
            "ESTNO": to_str(row.get("ESTNO", "")).strip(),
            "재고": to_int(row.get("재고수량")),
            "BL": to_str(row.get("BL번호", "")).strip(),

            "창고": to_str(row.get("창고", "")).strip(),
            "유통기한": to_date(row.get("유통기한")),
            "중량": to_float(row.get("중량")),
            "평중": to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고예정일")),
            "홀딩": to_str(row.get("비고")),

            "수집일": str(today),
            "상태": "없음",
            "메모": "",
        })


    print("DB 업로드 완료")