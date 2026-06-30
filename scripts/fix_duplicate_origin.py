"""
중복 원본행 정리: 같은 (BL, 상품명, 유통기한)의 비홀딩 행이 2개 이상인 경우
수량 합산 후 첫 번째 doc 유지, 나머지 삭제
"""
import sys, os
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(CRED))
db = firestore.client()

docs = [(d.id, d.to_dict()) for d in db.collection("all_data").stream()]

groups = defaultdict(list)
for doc_id, d in docs:
    if str(d.get("상태", "")).strip() == "holding":
        continue
    bl   = str(d.get("BL",    "")).strip()
    name = str(d.get("상품명", "")).strip()
    exp  = str(d.get("유통기한", "")).strip()
    key  = (bl, name, exp)
    groups[key].append((doc_id, d))

duplicates = {k: v for k, v in groups.items() if len(v) > 1}

if not duplicates:
    print("중복 원본행 없음")
    sys.exit(0)

for (bl, name, exp), rows in duplicates.items():
    total_qty = sum(int(r[1].get("재고", 0) or 0) for r in rows)
    keep_id, keep_data = rows[0]
    remove = rows[1:]

    print(f"[중복] BL={bl} | {name} | {exp}")
    print(f"  유지: {keep_id}  재고={keep_data.get('재고')}")
    for rid, rd in remove:
        print(f"  삭제: {rid}  재고={rd.get('재고')}")
    print(f"  합산 재고: {total_qty}박스")

    # 유지 doc 수량 업데이트
    db.collection("all_data").document(keep_id).update({"재고": total_qty})
    # 나머지 삭제
    for rid, _ in remove:
        db.collection("all_data").document(rid).delete()

    print(f"  → 완료\n")

print("정리 완료")
