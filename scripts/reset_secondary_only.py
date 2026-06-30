"""
Secondary all_data 초기화 + 파이프라인 상태 리셋
Primary는 할당량 초과 시 스킵
"""
import json, sys, os
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
BATCH_LIMIT    = 490

def _delete_collection(db, col_name, label):
    """지정 컬렉션 전체 삭제. employees는 절대 건드리지 않음."""
    assert col_name != "employees", "employees 컬렉션은 삭제 금지"
    col = db.collection(col_name)
    total = 0
    while True:
        docs = list(col.limit(BATCH_LIMIT).stream())
        if not docs:
            break
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        total += len(docs)
        sys.stdout.buffer.write(f"  [{label}] {col_name} {total}건 삭제...\n".encode("utf-8"))
        if len(docs) < BATCH_LIMIT:
            break
    return total


def _copy_employees(db_src, db_dst):
    """Primary employees → Secondary 복사 (Secondary 전환 시 직원 목록 유지)"""
    docs = list(db_src.collection("employees").stream())
    if not docs:
        return 0
    batch = db_dst.batch()
    for d in docs:
        batch.set(db_dst.collection("employees").document(d.id), d.to_dict())
    batch.commit()
    return len(docs)

# ── Primary 시도 (할당량 초과 시 스킵) ──────────────────
try:
    cred = credentials.Certificate(CRED_PRIMARY)
    try:
        app = firebase_admin.get_app("[DEFAULT]")
    except ValueError:
        app = firebase_admin.initialize_app(cred)
    db_pri = firestore.client(app)
    n = _delete_collection(db_pri, "all_data", "PRIMARY")
    sys.stdout.buffer.write(f"  [PRIMARY] 완료: {n}건 삭제 (employees 보존)\n".encode("utf-8"))
except Exception as e:
    if "Quota" in str(e) or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
        sys.stdout.buffer.write("  [PRIMARY] 할당량 초과 - 스킵 (나중에 따로 초기화 필요)\n".encode("utf-8"))
    else:
        sys.stdout.buffer.write(f"  [PRIMARY] 오류: {e}\n".encode("utf-8"))

# ── Secondary 초기화 ────────────────────────────────────
try:
    cred2 = credentials.Certificate(CRED_SECONDARY)
    try:
        app2 = firebase_admin.get_app("secondary")
    except ValueError:
        app2 = firebase_admin.initialize_app(cred2, name="secondary")
    db_sec = firestore.client(app2)
    n = _delete_collection(db_sec, "all_data", "SECONDARY")
    sys.stdout.buffer.write(f"  [SECONDARY] 완료: {n}건 삭제 (employees 보존)\n".encode("utf-8"))
except Exception as e:
    sys.stdout.buffer.write(f"  [SECONDARY] 오류: {e}\n".encode("utf-8"))

# ── 파이프라인 상태 초기화 ──────────────────────────────
for rel in ["pipeline/snapshot.pkl", "pipeline/active_db.json"]:
    p = ROOT / rel
    if p.exists():
        p.unlink()
        sys.stdout.buffer.write(f"  삭제: {rel}\n".encode("utf-8"))

# ── Secondary를 활성 DB로 설정 ──────────────────────────
now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
active_file = ROOT / "pipeline" / "active_db.json"
active_file.parent.mkdir(parents=True, exist_ok=True)
active_file.write_text(
    json.dumps({"active": "secondary", "switched_at": now_iso}, ensure_ascii=False),
    encoding="utf-8"
)

# Secondary에 마커 기록 (프론트엔드 전환용)
try:
    db_sec.collection("_meta").document("active_db").set({
        "active": "secondary", "switched_at": now_iso
    })
    sys.stdout.buffer.write("  [SECONDARY] _meta/active_db 마커 기록\n".encode("utf-8"))
except Exception as e:
    sys.stdout.buffer.write(f"  마커 기록 실패: {e}\n".encode("utf-8"))

# ── Primary employees → Secondary 복사 ─────────────────
try:
    cnt = _copy_employees(db_pri, db_sec)
    sys.stdout.buffer.write(f"  employees {cnt}명 Secondary 동기화 완료\n".encode("utf-8"))
except Exception as e:
    sys.stdout.buffer.write(f"  employees 복사 실패 (수동으로 sync_employees_to_secondary.py 실행): {e}\n".encode("utf-8"))

sys.stdout.buffer.write("\n초기화 완료. 서비스 재시작 후 Secondary에 새 데이터 업로드됩니다.\n".encode("utf-8"))
