"""
Primary employees 컬렉션 → Secondary 동기화
Primary 할당량이 있을 때 실행. Secondary 전환 시에도 직원 목록 유지.
"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED_PRIMARY   = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"

try:
    app_pri = firebase_admin.get_app("[DEFAULT]")
except ValueError:
    app_pri = firebase_admin.initialize_app(credentials.Certificate(CRED_PRIMARY))
db_pri = firestore.client(app_pri)

try:
    app_sec = firebase_admin.get_app("secondary")
except ValueError:
    app_sec = firebase_admin.initialize_app(credentials.Certificate(CRED_SECONDARY), name="secondary")
db_sec = firestore.client(app_sec)

docs = list(db_pri.collection("employees").stream())
if not docs:
    sys.stdout.buffer.write("Primary employees 없음\n".encode("utf-8"))
    sys.exit(0)

batch = db_sec.batch()
for d in docs:
    batch.set(db_sec.collection("employees").document(d.id), d.to_dict())
batch.commit()

sys.stdout.buffer.write(f"employees {len(docs)}명 Secondary 동기화 완료\n".encode("utf-8"))
