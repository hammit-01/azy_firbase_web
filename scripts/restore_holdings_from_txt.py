"""
holding_check_result.txt에서 홀딩 doc을 파싱해 Secondary에 복원
"""
import re, sys, os, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import firebase_admin
from firebase_admin import credentials, firestore

CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
TXT_FILE = ROOT / "scripts" / "holding_check_result.txt"

try:
    sec_app = firebase_admin.get_app("secondary")
except ValueError:
    sec_app = firebase_admin.initialize_app(credentials.Certificate(CRED_SECONDARY), name="secondary")
db = firestore.client(sec_app)

def _clean(s):
    return re.sub(r"[/\s]", "_", str(s).strip())

# Secondary에서 원본 doc 조회 (브랜드·등급 등 부가필드 확보)
sys.stdout.buffer.write("Secondary 원본 doc 조회 중...\n".encode("utf-8"))
orig_docs = {}
for d in db.collection("all_data").stream():
    data = d.to_dict()
    if str(data.get("상태", "")).strip() != "holding":
        bl   = str(data.get("BL", "")).strip()
        name = str(data.get("상품명", "")).strip()
        exp  = str(data.get("유통기한", "")).strip()
        orig_docs[(bl, name, exp)] = data

sys.stdout.buffer.write(f"  원본 {len(orig_docs)}건 로드\n".encode("utf-8"))

# 홀딩 상세 파싱: "미상:28박스(출고 미정)  송동근:100박스(출고 2026-07-01)"
def parse_detail(detail_str):
    entries = []
    for m in re.finditer(r'(.+?):(\d+)박스\(출고\s*([^)]+)\)', detail_str):
        holder = m.group(1).strip()
        qty    = int(m.group(2))
        date_s = m.group(3).strip()
        date   = "" if date_s == "미정" else date_s
        entries.append({"holder": holder, "qty": qty, "date": date})
    return entries

# 파일 파싱
lines = TXT_FILE.read_text(encoding="utf-8").splitlines()
holding_groups = []
for line in lines:
    # 데이터 행: BL번호로 시작 (영문+숫자)
    m = re.match(
        r'^(\S+)\s+(.+?)\s+(\d{4}-\d{2}-\d{2})\s+\d+\s+(\d+)\s+\d+\s{2}(.+?)(?:\s+★.*)?$',
        line
    )
    if not m:
        continue
    bl      = m.group(1).strip()
    name    = m.group(2).strip()
    exp     = m.group(3).strip()
    h_total = int(m.group(4))
    detail  = m.group(5).strip()
    entries = parse_detail(detail)
    if not entries:
        # 파싱 실패 시 통짜 1건으로 처리
        entries = [{"holder": "미상", "qty": h_total, "date": ""}]
    holding_groups.append({"bl": bl, "name": name, "exp": exp, "entries": entries})

sys.stdout.buffer.write(f"파싱된 홀딩 그룹: {len(holding_groups)}건\n".encode("utf-8"))

# Secondary에 홀딩 doc 생성
created = 0
batch = db.batch()
batch_count = 0

for g in holding_groups:
    bl, name, exp = g["bl"], g["name"], g["exp"]
    orig = orig_docs.get((bl, name, exp), {})

    for entry in g["entries"]:
        doc_id  = str(uuid.uuid4())  # holding은 auto-gen ID
        doc_ref = db.collection("all_data").document(doc_id)
        batch.set(doc_ref, {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": name,
            "브랜드": orig.get("브랜드", ""),
            "등급":   orig.get("등급", ""),
            "ESTNO":  orig.get("ESTNO", ""),
            "재고":   entry["qty"],
            "BL":     bl,
            "창고":   orig.get("창고", ""),
            "유통기한": exp,
            "중량":   orig.get("중량", ""),
            "평중":   orig.get("평중", ""),
            "출고일": entry["date"],
            "홀딩":   entry["holder"],
            "수집일": "",
            "상태":   "holding",
            "메모":   "",
        })
        batch_count += 1
        created += 1

        if batch_count >= 490:
            batch.commit()
            batch = db.batch()
            batch_count = 0

if batch_count > 0:
    batch.commit()

msg = f"완료: 홀딩 {created}건 Secondary 복원\n"
sys.stdout.buffer.write(msg.encode("utf-8"))
