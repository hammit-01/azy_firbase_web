"""
Primary Firestore에서 employees 컬렉션을 읽어 텍스트 파일로 저장
Primary 할당량 초기화 후 실행: python scripts/export_employees.py
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import firebase_admin
from firebase_admin import credentials, firestore

CRED = ROOT / "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
OUT  = ROOT / "scripts" / "employees_backup.txt"

if not CRED.exists():
    print(f"크레덴셜 없음: {CRED}")
    sys.exit(1)

try:
    app = firebase_admin.get_app("[DEFAULT]")
except ValueError:
    app = firebase_admin.initialize_app(credentials.Certificate(str(CRED)))
db = firestore.client(app)

print("Primary employees 조회 중...")
docs = list(db.collection("employees").stream())
if not docs:
    print("employees 없음")
    sys.exit(0)

lines = []
lines.append(f"# employees 백업 — {datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S KST')}")
lines.append(f"# 총 {len(docs)}명")
lines.append("")
for d in sorted(docs, key=lambda x: x.to_dict().get("번호", 0)):
    data = d.to_dict()
    lines.append(json.dumps(data, ensure_ascii=False))

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"저장 완료: {OUT} ({len(docs)}명)")
for d in sorted(docs, key=lambda x: x.to_dict().get("번호", 0)):
    print(" ", d.to_dict())
