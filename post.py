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

    # ── 업로드 전 집계: (BL번호, 수탁품, 유통기한) 기준으로 재고수량 합산 ──
    # EDA pk는 코드+BL+유통기한이라 창고 코드가 다르면 별개 row로 들어오지만
    # 실제로는 같은 상품이므로 여기서 한 번 더 합산해 중복 업로드 방지
    agg_cols = ["BL번호", "수탁품", "유통기한"]
    numeric_cols = [c for c in ["재고수량"] if c in df.columns]
    first_cols   = [c for c in df.columns if c not in agg_cols + numeric_cols]

    df["재고수량"] = pd.to_numeric(
        df["재고수량"].astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    ).fillna(0).astype(int)

    qty_sum  = df.groupby(agg_cols, dropna=False, sort=False)["재고수량"].sum().reset_index()
    first_df = df.drop_duplicates(subset=agg_cols, keep="first")[agg_cols + first_cols]
    df = first_df.merge(qty_sum, on=agg_cols, how="left").reset_index(drop=True)
    # ────────────────────────────────────────────────────────────────────────

    # 기존 홀딩 행 선조회: (BL, 상품명, 유통기한) → 홀딩 수량 합계
    # 수집일=="" 조건으로 holding 행 식별 (한국어 필드명 서버 쿼리 우회)
    holding_sum: dict = {}
    from google.cloud.firestore_v1.base_query import FieldFilter
    for hdoc in db.collection("all_data").where(filter=FieldFilter("`수집일`", "==", "")).stream():
        h = hdoc.to_dict()
        if str(h.get("상태", "")).strip() != "holding":
            continue
        key = (
            str(h.get("BL",    "")).strip(),
            str(h.get("상품명", "")).strip(),
            str(h.get("유통기한", "")).strip(),
        )
        holding_sum[key] = holding_sum.get(key, 0) + int(h.get("재고", 0) or 0)

    # 오늘 데이터 업로드 — doc_id를 BL+상품명+유통기한 기반으로 생성 (일관성 확보)
    skipped = 0
    for _, row in df.iterrows():
        code_val   = to_str(row.get("코드", "")).strip()
        bl_val     = to_str(row.get("BL번호", "")).strip()
        est_val    = to_str(row.get("식별번호", "")).strip()
        name_val   = to_str(row.get("수탁품", "")).strip()
        expire_val = to_date(row.get("유통기한"))

        # doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한
        expire_str = expire_val.replace("-", "") if expire_val else ""
        bl_last4   = (bl_val[-4:] if len(bl_val) >= 4 else bl_val).replace("/", "_").replace(" ", "_")
        est_last4  = ((est_val[-4:] if len(est_val) >= 4 else est_val).replace("/", "_").replace(" ", "_")) if est_val else ""
        code_clean = code_val.replace("/", "_").replace(" ", "_")
        doc_id = f"{code_clean}_{bl_last4}_{est_last4}_{expire_str}"

        crawled_qty = to_int(row.get("재고수량"))
        h_qty = holding_sum.get((bl_val, name_val, expire_val), 0)
        net_qty = crawled_qty - h_qty

        if net_qty <= 0:
            # 전량 홀딩 중 → 원본 행 업로드 불필요
            skipped += 1
            continue

        doc_ref = db.collection("all_data").document(doc_id)
        doc_ref.set({
            "id":    doc_ref.id,
            "pk":    doc_ref.id,
            "상품명": name_val,
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO": to_str(row.get("ESTNO", "")).strip(),
            "재고":   net_qty,
            "BL":    bl_val,
            "창고":   to_str(row.get("창고", "")).strip(),
            "유통기한": expire_val,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고예정일")),
            "홀딩":   to_str(row.get("비고")),
            "수집일": str(today),
            "상태":   "없음",
            "메모":   "",
        })

    print(f"DB 업로드 완료 (홀딩 차감 스킵: {skipped}건)")