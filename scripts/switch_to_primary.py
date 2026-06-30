"""
Primary Firebase로 복귀: Secondary _meta/active_db 마커 삭제 + active_db.json 제거
"""
import sys, os, json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
ACTIVE_DB_FILE = ROOT / "pipeline" / "active_db.json"

try:
    sec_app = firebase_admin.get_app("secondary")
except ValueError:
    sec_app = firebase_admin.initialize_app(credentials.Certificate(CRED_SECONDARY), name="secondary")
db = firestore.client(sec_app)

# 마커 삭제 → 프론트엔드 onSnapshot이 감지 → Primary로 자동 리로드
db.collection("_meta").document("active_db").delete()

# 로컬 상태 파일 삭제
if ACTIVE_DB_FILE.exists():
    ACTIVE_DB_FILE.unlink()

sys.stdout.buffer.write("[완료] Primary 복귀\n  Secondary _meta/active_db 마커 삭제\n  pipeline/active_db.json 삭제\n".encode("utf-8"))
