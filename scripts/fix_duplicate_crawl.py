"""
같은 날 pk 형식 변경 후 재업로드로 생긴 중복 크롤링 문서를 제거.
holding 행(수집일="")은 절대 건드리지 않음.
PRIMARY / SECONDARY 모두 처리.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import firebase_admin
from firebase_admin import credentials, firestore

CRED_PRIMARY   = ROOT / "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
CRED_SECONDARY = ROOT / "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
BATCH_LIMIT    = 400


def _fix_db(cred_path, label, app_name):
    if not Path(cred_path).exists():
        print(f"[{label}] 크레덴셜 없음, 스킵")
        return

    cred = credentials.Certificate(str(cred_path))
    try:
        app = firebase_admin.get_app(app_name)
    except ValueError:
        if app_name == "[DEFAULT]":
            app = firebase_admin.initialize_app(cred)
        else:
            app = firebase_admin.initialize_app(cred, name=app_name)
    db = firestore.client(app)

    print(f"[{label}] all_data 전체 조회 중...")
    docs = list(db.collection("all_data").stream())
    print(f"[{label}] 총 {len(docs)}건")

    # 수집일이 있는(크롤링) 문서만 삭제 대상
    to_delete = [d for d in docs if d.to_dict().get("수집일")]
    holding_count = len(docs) - len(to_delete)
    print(f"[{label}] 크롤링 문서: {len(to_delete)}건 / 홀딩 문서: {holding_count}건")

    if not to_delete:
        print(f"[{label}] 삭제 대상 없음")
        return

    # pk 형식별 분류 (디버깅용)
    old_fmt, new_fmt, unknown = [], [], []
    for d in to_delete:
        pk = d.id
        parts = pk.split("_")
        if len(parts) >= 4 and parts[0].isalpha() and len(parts[0]) >= 2:
            new_fmt.append(d)
        elif len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 4:
            old_fmt.append(d)
        else:
            unknown.append(d)

    print(f"[{label}]   구 pk 형식: {len(old_fmt)}건")
    print(f"[{label}]   신 pk 형식: {len(new_fmt)}건")
    print(f"[{label}]   불명 형식:  {len(unknown)}건")

    answer = input(f"\n[{label}] 크롤링 문서 {len(to_delete)}건을 모두 삭제하고 재업로드하시겠습니까? (yes/no): ").strip()
    if answer.lower() != "yes":
        print(f"[{label}] 취소")
        return

    deleted = 0
    for i in range(0, len(to_delete), BATCH_LIMIT):
        chunk = to_delete[i:i + BATCH_LIMIT]
        batch = db.batch()
        for d in chunk:
            batch.delete(d.reference)
        batch.commit()
        deleted += len(chunk)
        print(f"[{label}]   {deleted}/{len(to_delete)} 삭제...")

    print(f"[{label}] 완료 — {deleted}건 삭제, 홀딩 {holding_count}건 보존")


if __name__ == "__main__":
    print("=" * 55)
    print("크롤링 중복 문서 정리 (홀딩 보존)")
    print("=" * 55)
    _fix_db(CRED_PRIMARY,   "PRIMARY",   "[DEFAULT]")
    print()
    _fix_db(CRED_SECONDARY, "SECONDARY", "secondary")
    print()
    print("완료. 이후 파이프라인을 재실행하세요: python main.py")
