"""
Primary의 홀딩 doc을 Secondary로 복사
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
    pri_app = firebase_admin.get_app("[DEFAULT]")
except ValueError:
    pri_app = firebase_admin.initialize_app(credentials.Certificate(CRED_PRIMARY))
db_pri = firestore.client(pri_app)

try:
    sec_app = firebase_admin.get_app("secondary")
except ValueError:
    sec_app = firebase_admin.initialize_app(credentials.Certificate(CRED_SECONDARY), name="secondary")
db_sec = firestore.client(sec_app)

# Primary에서 홀딩 doc만 조회 (필터 쿼리 → 전체 스트림보다 적은 읽기 소모)
try:
    from google.cloud.firestore_v1.base_query import FieldFilter
    holding_docs = list(
        db_pri.collection("all_data")
              .where(filter=FieldFilter("상태", "==", "holding"))
              .stream()
    )
except Exception as e:
    sys.stdout.buffer.write(f"Primary 홀딩 조회 실패: {e}\n".encode("utf-8"))
    sys.exit(1)

if not holding_docs:
    sys.stdout.buffer.write("Primary에 홀딩 데이터 없음\n".encode("utf-8"))
    sys.exit(0)

# Secondary에 배치 복사 (auto-gen ID 그대로 유지)
BATCH_LIMIT = 490
for i in range(0, len(holding_docs), BATCH_LIMIT):
    batch = db_sec.batch()
    for doc in holding_docs[i:i + BATCH_LIMIT]:
        batch.set(db_sec.collection("all_data").document(doc.id), doc.to_dict())
    batch.commit()

msg = f"홀딩 {len(holding_docs)}건 Secondary 복사 완료\n"
sys.stdout.buffer.write(msg.encode("utf-8"))
