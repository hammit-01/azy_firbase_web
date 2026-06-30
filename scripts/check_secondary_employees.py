import sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import firebase_admin
from firebase_admin import credentials, firestore

CRED_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
try:
    app = firebase_admin.get_app("secondary")
except ValueError:
    app = firebase_admin.initialize_app(credentials.Certificate(CRED_SECONDARY), name="secondary")
db = firestore.client(app)

docs = list(db.collection("employees").stream())
if docs:
    for d in docs:
        sys.stdout.buffer.write(f"  {d.to_dict()}\n".encode("utf-8"))
else:
    sys.stdout.buffer.write("Secondary employees 없음\n".encode("utf-8"))
