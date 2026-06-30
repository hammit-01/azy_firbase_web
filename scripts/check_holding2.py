"""
Firestore all_data 홀딩 수량 검증 - UTF-8 파일 출력
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

docs = [d.to_dict() for d in db.collection("all_data").stream()]

groups = defaultdict(lambda: {"원본행들": [], "홀딩행들": []})

for d in docs:
    bl    = str(d.get("BL",    "")).strip()
    name  = str(d.get("상품명", "")).strip()
    exp   = str(d.get("유통기한", "")).strip()
    qty   = int(d.get("재고", 0) or 0)
    state = str(d.get("상태", "")).strip()
    key   = (bl, name, exp)

    if state == "holding":
        groups[key]["홀딩행들"].append({
            "수량": qty,
            "홀딩자": d.get("홀딩", ""),
            "출고일": d.get("출고일", ""),
        })
    else:
        groups[key]["원본행들"].append(qty)

lines = []
lines.append(f"{'BL':<24} {'상품명':<18} {'유통기한':<12} {'원본':>6} {'홀딩합':>6} {'합계':>6}  홀딩 상세")
lines.append("-" * 110)

total_orig = total_hold = 0
warn_count = 0

for (bl, name, exp), v in sorted(groups.items()):
    if not v["홀딩행들"]:
        continue
    orig   = sum(v["원본행들"])
    h_tot  = sum(h["수량"] for h in v["홀딩행들"])
    total  = orig + h_tot
    total_orig += orig
    total_hold += h_tot

    detail = "  ".join(
        f"{h['홀딩자'] or '미상'}:{h['수량']}박스(출고 {h['출고일'] or '미정'})"
        for h in v["홀딩행들"]
    )

    warn = ""
    # 원본행이 여러 개면 이상 (중복 업로드 의심)
    if len(v["원본행들"]) > 1:
        warn = " ★중복원본"
        warn_count += 1

    lines.append(f"{bl:<24} {name:<18} {exp:<12} {orig:>6} {h_tot:>6} {total:>6}  {detail}{warn}")

lines.append("-" * 110)
lines.append(f"{'합계':<56} {total_orig:>6} {total_hold:>6} {total_orig+total_hold:>6}")
if warn_count:
    lines.append(f"\n★ 중복 원본행 {warn_count}건 발견 — post.py 중복 업로드 의심")

out = "\n".join(lines)
out_path = ROOT / "scripts" / "holding_check_result.txt"
out_path.write_text(out, encoding="utf-8")
sys.stdout.buffer.write((out + f"\n\n결과 저장: {out_path}\n").encode("utf-8"))
