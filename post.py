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
    """수집일이 있는(크롤링) all_data 문서를 처리:
    - 이전 날짜 → archive_data로 이동
    - 오늘 날짜  → 그냥 삭제 (같은 날 재실행 시 구 pk 문서 제거)
    홀딩 행(수집일="")은 절대 건드리지 않음.
    """
    docs = list(db.collection("all_data").stream())
    to_archive = []
    to_delete_today = []

    for d in docs:
        col_date = d.to_dict().get("수집일")
        if not col_date:          # 홀딩 행 (수집일 == "")
            continue
        if col_date == today:
            to_delete_today.append(d)   # 오늘 것 → 삭제 후 재업로드
        else:
            to_archive.append(d)        # 이전 날짜 → 아카이브

    BATCH_LIMIT = 250

    if to_archive:
        archive_ref = db.collection("archive_data")
        for i in range(0, len(to_archive), BATCH_LIMIT):
            chunk = to_archive[i:i + BATCH_LIMIT]
            batch = db.batch()
            for doc in chunk:
                batch.set(archive_ref.document(doc.id), doc.to_dict())
                batch.delete(doc.reference)
            batch.commit()
        print(f"이전 데이터 {len(to_archive)}개 archive_data로 이동 완료")
    else:
        print("아카이브할 이전 데이터 없음")

    if to_delete_today:
        for i in range(0, len(to_delete_today), BATCH_LIMIT):
            chunk = to_delete_today[i:i + BATCH_LIMIT]
            batch = db.batch()
            for doc in chunk:
                batch.delete(doc.reference)
            batch.commit()
        print(f"오늘자 기존 크롤링 데이터 {len(to_delete_today)}개 삭제 (재업로드 전 정리)")


def post(df):
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    # Firebase 초기화
    cred = credentials.Certificate("azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # 이전 날짜 데이터 아카이브
    _archive_old_data(db, today)

    # ── 업로드 전 집계: (BL번호, 수탁품, 유통기한, 창고) 기준으로 재고수량 합산 ──
    # 같은 창고 내 동일 상품 중복 행은 합산, 창고가 다르면 별개 행으로 유지
    agg_cols = ["BL번호", "수탁품", "유통기한", "창고"]
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
    # _archive_old_data 이후에는 all_data에 홀딩 문서만 남으므로 전체 스캔
    holding_sum: dict = {}
    for hdoc in db.collection("all_data").stream():
        h = hdoc.to_dict()
        if str(h.get("상태", "")).strip() != "holding":
            continue
        key = (
            str(h.get("BL",    "")).strip(),
            str(h.get("상품명", "")).strip(),
            str(h.get("유통기한", "")).strip(),
            str(h.get("창고",   "")).strip(),
        )
        holding_sum[key] = holding_sum.get(key, 0) + int(h.get("재고", 0) or 0)

    # 오늘 데이터 업로드 — doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한_창고
    skipped = 0
    for _, row in df.iterrows():
        code_val   = to_str(row.get("코드", "")).strip()
        bl_val     = to_str(row.get("BL번호", "")).strip()
        est_val    = to_str(row.get("식별번호", "")).strip()
        name_val   = to_str(row.get("수탁품", "")).strip()
        expire_val = to_date(row.get("유통기한"))
        wh_val     = to_str(row.get("창고", "")).strip()

        # doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한_창고
        expire_str = expire_val.replace("-", "") if expire_val else ""
        bl_last4   = (bl_val[-4:] if len(bl_val) >= 4 else bl_val).replace("/", "_").replace(" ", "_")
        est_last4  = ((est_val[-4:] if len(est_val) >= 4 else est_val).replace("/", "_").replace(" ", "_")) if est_val else ""
        code_clean = code_val.replace("/", "_").replace(" ", "_")
        wh_clean   = wh_val.replace("/", "_").replace(" ", "_")
        doc_id = f"{code_clean}_{bl_last4}_{est_last4}_{expire_str}_{wh_clean}"

        crawled_qty = to_int(row.get("재고수량"))
        h_qty = holding_sum.get((bl_val, name_val, expire_val, wh_val), 0)
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