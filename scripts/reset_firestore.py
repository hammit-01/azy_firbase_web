"""
Firestore all_data 컬렉션 전체 삭제 + 파이프라인 상태 초기화
Primary / Secondary 양쪽 모두 처리.
employees 컬렉션은 절대 삭제하지 않음.
"""
import json
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED_PRIMARY   = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
COLLECTION     = "all_data"
BATCH_LIMIT    = 500


def _delete_collection(db, col_name):
    """지정 컬렉션 전체 삭제. employees는 절대 건드리지 않음."""
    assert col_name != "employees", "employees 컬렉션은 삭제 금지"
    col_ref = db.collection(col_name)
    total = 0
    while True:
        docs = list(col_ref.limit(BATCH_LIMIT).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        total += len(docs)
        print(f"    {total}건 삭제...")
        if len(docs) < BATCH_LIMIT:
            break
    return total


def _copy_employees(db_src, db_dst, src_label, dst_label):
    """employees 컬렉션을 src에서 dst로 복사"""
    docs = list(db_src.collection("employees").stream())
    if not docs:
        print(f"  [{src_label}] employees 없음 - 스킵")
        return
    batch = db_dst.batch()
    for d in docs:
        batch.set(db_dst.collection("employees").document(d.id), d.to_dict())
    batch.commit()
    print(f"  [{dst_label}] employees {len(docs)}명 복사 완료")


def reset_db(cred_path, label, app_name):
    if not Path(cred_path).exists():
        print(f"  [{label}] 크레덴셜 없음, 스킵: {cred_path}")
        return
    cred = credentials.Certificate(cred_path)
    try:
        app = firebase_admin.get_app(app_name)
    except ValueError:
        if app_name == "[DEFAULT]":
            app = firebase_admin.initialize_app(cred)
        else:
            app = firebase_admin.initialize_app(cred, name=app_name)
    db = firestore.client(app)

    print(f"  [{label}] {COLLECTION} 삭제 중...")
    total = _delete_collection(db, COLLECTION)
    print(f"  [{label}] {total}건 삭제 완료")

    try:
        db.collection("_meta").document("active_db").delete()
        print(f"  [{label}] _meta/active_db 마커 삭제")
    except Exception as e:
        print(f"  [{label}] 마커 삭제 실패 (무시): {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Firestore 컬렉션 초기화")
    print("=" * 50)

    # 현재 활성 DB 표시
    active_file = ROOT / "pipeline" / "active_db.json"
    active = "primary"
    if active_file.exists():
        try:
            active = json.loads(active_file.read_text(encoding="utf-8")).get("active", "primary")
        except Exception:
            pass
    print(f"현재 활성 DB: {active.upper()}")
    print()

    reset_db(CRED_PRIMARY,   "PRIMARY",   "[DEFAULT]")
    print()
    reset_db(CRED_SECONDARY, "SECONDARY", "secondary")
    print()

    # Primary employees → Secondary 동기화 (Secondary 전환 시 직원 목록 유지)
    print("=" * 50)
    print("employees 동기화 (Primary → Secondary)")
    print("=" * 50)
    try:
        pri_app = firebase_admin.get_app("[DEFAULT]")
        sec_app = firebase_admin.get_app("secondary")
        _copy_employees(firestore.client(pri_app), firestore.client(sec_app), "PRIMARY", "SECONDARY")
    except Exception as e:
        print(f"  employees 동기화 실패 (무시): {e}")

    print()
    print("=" * 50)
    print("파이프라인 상태 초기화")
    print("=" * 50)

    for rel in ["pipeline/snapshot.pkl", "pipeline/active_db.json"]:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            print(f"  삭제: {rel}")
        else:
            print(f"  없음 (스킵): {rel}")

    print()
    print("완료! 재시작하려면:")
    print("  python run_service.py")
