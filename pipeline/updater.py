import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

log = logging.getLogger("updater")

CRED_PATH   = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
COLLECTION  = "all_data"
BATCH_LIMIT = 250   # set + delete 각 1 op → 250 docs = 250 ops (한도 500)

_db      = None
_db_lock = threading.Lock()


def _get_db():
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                cred = credentials.Certificate(CRED_PATH)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                _db = firestore.client()
    return _db


def _df_to_dict(df: pd.DataFrame, today: str) -> dict:
    from post import to_str, to_int, to_float, to_date
    result = {}
    for _, row in df.iterrows():
        bl     = to_str(row.get("BL번호", "")).strip()
        weight = to_str(row.get("평균중량", "")).strip().replace(".", "")
        expire = to_date(row.get("유통기한"))

        bl_last4   = (bl[-4:] if len(bl) >= 4 else bl).replace("/", "_")
        expire_str = (expire.replace("-", "") if expire else "").replace("/", "_")
        weight_str = weight.replace("/", "_")
        doc_id     = f"{bl_last4}_{expire_str}_{weight_str}"

        if not doc_id or doc_id == "__":
            continue

        data = {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": to_str(row.get("수탁품", "")).strip(),
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO":  to_str(row.get("ESTNO", "")).strip(),
            "재고":   to_int(row.get("재고수량")),
            "BL":     bl,
            "창고":   to_str(row.get("창고", "")).strip(),
            "유통기한": expire,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고일")),
            "홀딩":   to_str(row.get("홀딩", "")),
            "수집일": today,
            "상태":   "없음",
            "메모":   "",
        }
        result[doc_id] = data
    return result


def _batch_upsert(db, items: dict):
    keys = list(items.keys())
    for i in range(0, len(keys), BATCH_LIMIT):
        batch = db.batch()
        for pk in keys[i:i + BATCH_LIMIT]:
            batch.set(db.collection(COLLECTION).document(pk), items[pk])
        batch.commit()


def _batch_delete(db, pks: list):
    for i in range(0, len(pks), BATCH_LIMIT):
        batch = db.batch()
        for pk in pks[i:i + BATCH_LIMIT]:
            batch.delete(db.collection(COLLECTION).document(pk))
        batch.commit()


class FirestoreUpdater:
    def update_diff(self, new_df: pd.DataFrame, prev_snapshot: dict) -> int:
        db    = _get_db()
        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

        new_data  = _df_to_dict(new_df, today)
        to_upsert = {}
        to_delete = []

        for pk, data in new_data.items():
            if pk not in prev_snapshot or prev_snapshot[pk] != data:
                to_upsert[pk] = data

        for pk in prev_snapshot:
            if pk not in new_data:
                to_delete.append(pk)

        total = len(to_upsert) + len(to_delete)

        if total == 0:
            log.info("  변경 없음")
            return 0

        if to_upsert:
            _batch_upsert(db, to_upsert)
        if to_delete:
            _batch_delete(db, to_delete)

        log.info(f"  Firestore ↑{len(to_upsert)}건 업서트 / ✕{len(to_delete)}건 삭제")
        return total
