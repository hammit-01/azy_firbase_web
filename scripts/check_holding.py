"""
Firestore all_data 홀딩 수량 검증
- 홀딩 행과 원본 행의 (BL, 상품명, 유통기한) 기준 수량 합산 확인
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"

cred = credentials.Certificate(CRED)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

docs = [d.to_dict() for d in db.collection("all_data").stream()]

# (BL, 상품명, 유통기한) 기준으로 그룹핑
from collections import defaultdict

groups = defaultdict(lambda: {"원본": 0, "홀딩": [], "원본_rows": []})

for d in docs:
    bl    = str(d.get("BL",    "")).strip()
    name  = str(d.get("상품명", "")).strip()
    exp   = str(d.get("유통기한", "")).strip()
    qty   = int(d.get("재고", 0) or 0)
    state = str(d.get("상태", "")).strip()
    key   = (bl, name, exp)

    if state == "holding":
        groups[key]["홀딩"].append({"수량": qty, "홀딩자": d.get("홀딩", ""), "출고일": d.get("출고일", "")})
    else:
        groups[key]["원본"] += qty
        groups[key]["원본_rows"].append(qty)

print(f"{'BL':<20} {'상품명':<16} {'유통기한':<12} {'원본':>6} {'홀딩합':>6} {'합계':>6}  홀딩내역")
print("-" * 100)

total_orig = total_hold = 0
for (bl, name, exp), v in sorted(groups.items()):
    if not v["홀딩"]:
        continue  # 홀딩 없는 행은 표시 안 함
    h_total = sum(h["수량"] for h in v["홀딩"])
    orig    = v["원본"]
    total   = orig + h_total
    total_orig += orig
    total_hold += h_total

    hold_detail = "  ".join(f"{h['홀딩자']}:{h['수량']}박스(출고{h['출고일'] or '미정'})" for h in v["홀딩"])
    print(f"{bl:<20} {name:<16} {exp:<12} {orig:>6} {h_total:>6} {total:>6}  {hold_detail}")

print("-" * 100)
print(f"{'합계':<50} {total_orig:>6} {total_hold:>6} {total_orig+total_hold:>6}")
