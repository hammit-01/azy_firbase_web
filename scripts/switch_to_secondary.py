"""
Secondary Firebase로 전환: _meta/active_db 마커 기록 + active_db.json 생성
Primary 할당량 초과 시 실행
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED_PRIMARY   = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
ACTIVE_DB_FILE = ROOT / "pipeline" / "active_db.json"

if not Path(CRED_SECONDARY).exists():
    sys.stdout.buffer.write(f"오류: {CRED_SECONDARY} 없음\n".encode("utf-8"))
    sys.exit(1)

cred_sec = credentials.Certificate(CRED_SECONDARY)
try:
    app_sec = firebase_admin.get_app("secondary")
except ValueError:
    app_sec = firebase_admin.initialize_app(cred_sec, name="secondary")
db_sec = firestore.client(app_sec)

now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()

# ── Primary employees → Secondary 복사 (Primary 접근 가능한 경우) ──
try:
    cred_pri = credentials.Certificate(CRED_PRIMARY)
    try:
        app_pri = firebase_admin.get_app("[DEFAULT]")
    except ValueError:
        app_pri = firebase_admin.initialize_app(cred_pri)
    db_pri = firestore.client(app_pri)
    emp_docs = list(db_pri.collection("employees").stream())
    if emp_docs:
        batch = db_sec.batch()
        for d in emp_docs:
            batch.set(db_sec.collection("employees").document(d.id), d.to_dict())
        batch.commit()
        sys.stdout.buffer.write(f"  employees {len(emp_docs)}명 Secondary 동기화\n".encode("utf-8"))
except Exception as e:
    sys.stdout.buffer.write(f"  employees 동기화 실패 (Primary 할당량 초과일 수 있음): {e}\n".encode("utf-8"))

# ── Secondary에 마커 기록 → 프론트엔드가 감지하고 자동 리로드 ──
db_sec.collection("_meta").document("active_db").set({
    "active": "secondary",
    "switched_at": now_iso,
})

# 로컬 상태 파일 저장
ACTIVE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
ACTIVE_DB_FILE.write_text(
    json.dumps({"active": "secondary", "switched_at": now_iso}, ensure_ascii=False),
    encoding="utf-8"
)

msg = f"[완료] Secondary DB 전환\n  마커: _meta/active_db → active=secondary\n  파일: {ACTIVE_DB_FILE}\n  시각: {now_iso}\n"
sys.stdout.buffer.write(msg.encode("utf-8"))
