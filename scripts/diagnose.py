"""
현재 Firestore 수량 진단: 홀딩 포함 전체 합산 vs 원본 단독
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

groups = defaultdict(lambda: {"원본": [], "홀딩": []})
for doc_id, d in docs:
    bl   = str(d.get("BL", "")).strip()
    name = str(d.get("상품명", "")).strip()
    exp  = str(d.get("유통기한", "")).strip()
    qty  = int(d.get("재고", 0) or 0)
    state= str(d.get("상태", "")).strip()
    key  = (bl, name, exp)
    if state == "holding":
        groups[key]["홀딩"].append((doc_id, qty))
    else:
        groups[key]["원본"].append((doc_id, qty))

lines = []
lines.append(f"{'BL':<24} {'상품명':<18} {'유통기한':<12} {'원본수':>5} {'원본합':>6} {'홀딩수':>5} {'홀딩합':>6} {'총합':>6}  문제")
lines.append("-" * 110)

total_orig = total_hold = warn = 0
for (bl, name, exp), v in sorted(groups.items()):
    orig_rows = v["원본"]
    hold_rows = v["홀딩"]
    o_sum = sum(q for _, q in orig_rows)
    h_sum = sum(q for _, q in hold_rows)
    total = o_sum + h_sum
    total_orig += o_sum
    total_hold += h_sum

    issues = []
    if len(orig_rows) > 1:
        issues.append(f"원본중복({len(orig_rows)}개)")
    if len(hold_rows) > 1:
        issues.append(f"홀딩중복({len(hold_rows)}개)")

    if issues or len(orig_rows) > 1 or len(hold_rows) > 1:
        warn += 1
        lines.append(f"{bl:<24} {name:<18} {exp:<12} {len(orig_rows):>5} {o_sum:>6} {len(hold_rows):>5} {h_sum:>6} {total:>6}  {'  '.join(issues)}")

lines.append("-" * 110)
lines.append(f"{'문제 있는 그룹':<56} {warn}건")
lines.append(f"{'전체 원본 합계':<56} {total_orig}박스")
lines.append(f"{'전체 홀딩 합계':<56} {total_hold}박스")
lines.append(f"{'전체 총합':<56} {total_orig+total_hold}박스")

out = "\n".join(lines)
out_path = ROOT / "scripts" / "diagnose_result.txt"
out_path.write_text(out, encoding="utf-8")
sys.stdout.buffer.write((out + "\n").encode("utf-8"))
