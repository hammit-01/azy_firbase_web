"""
Firestore all_data 비홀딩 행 정리:
  - (BL, 상품명, 유통기한) 기준으로 중복 합산
  - 기존 doc 삭제 → 새 doc_id(BL_유통기한_상품명)로 재생성
  - 홀딩 행(state=holding)은 건드리지 않음
"""
import sys, os, re
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

BATCH_LIMIT = 490  # Firestore batch 최대 500 ops

def clean(s):
    return re.sub(r"[/\s]", "_", str(s).strip())

# 1. 전체 비홀딩 행 로드
print("Firestore 조회 중...")
all_docs = [(d.id, d.to_dict()) for d in db.collection("all_data").stream()
            if str(d.to_dict().get("상태", "")).strip() != "holding"]
print(f"  비홀딩 행 {len(all_docs)}건")

# 2. (BL, 상품명, 유통기한) 기준 그룹핑
groups = defaultdict(list)
for doc_id, data in all_docs:
    bl   = str(data.get("BL",    "")).strip()
    name = str(data.get("상품명", "")).strip()
    exp  = str(data.get("유통기한", "")).strip()
    groups[(bl, name, exp)].append((doc_id, data))

# 3. 새 doc_id 생성 함수
def new_doc_id(bl, name, exp):
    expire_str = exp.replace("-", "")
    return f"{clean(bl)}_{expire_str}_{clean(name)}"

# 4. 배치로 삭제 + 생성
print(f"  그룹 수: {len(groups)}")

ops = []  # (action, ref, data)
merged = dup = 0

for (bl, name, exp), rows in groups.items():
    total_qty = sum(int(r[1].get("재고", 0) or 0) for r in rows)
    # 대표 데이터: 첫 번째 row 기준
    _, rep = rows[0]

    target_id = new_doc_id(bl, name, exp)

    # 기존 doc 전부 삭제 예약
    for old_id, _ in rows:
        if old_id != target_id:  # 이미 올바른 id면 삭제 후 재생성 불필요
            ops.append(("delete", db.collection("all_data").document(old_id), None))
        if len(rows) > 1:
            dup += 1

    # 새 doc 생성/업데이트 예약
    ops.append(("set", db.collection("all_data").document(target_id), {
        "id":    target_id,
        "pk":    target_id,
        "상품명": name,
        "브랜드": str(rep.get("브랜드", "")).strip(),
        "등급":   str(rep.get("등급",   "")).strip(),
        "ESTNO": str(rep.get("ESTNO",  "")).strip(),
        "재고":   total_qty,
        "BL":    bl,
        "창고":   str(rep.get("창고",   "")).strip(),
        "유통기한": exp,
        "중량":   rep.get("중량",   ""),
        "평중":   rep.get("평중",   ""),
        "출고일": str(rep.get("출고일", "")).strip(),
        "홀딩":   str(rep.get("홀딩",   "")).strip(),
        "수집일": str(rep.get("수집일", "")).strip(),
        "상태":   "없음",
        "메모":   str(rep.get("메모",   "")).strip(),
    }))

    if len(rows) > 1:
        merged += 1

# 5. 배치 실행
print(f"  처리 예정: {len(ops)}건 (중복 그룹 {merged}개, 삭제 예정 {dup}건)")
for i in range(0, len(ops), BATCH_LIMIT):
    chunk = ops[i:i + BATCH_LIMIT]
    batch = db.batch()
    for action, ref, data in chunk:
        if action == "delete":
            batch.delete(ref)
        else:
            batch.set(ref, data)
    batch.commit()
    print(f"  배치 커밋 {i + len(chunk)}/{len(ops)}")

print(f"\n완료: 중복 합산 {merged}그룹, 구 doc 삭제 {dup}건")
