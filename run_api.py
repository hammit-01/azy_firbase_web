"""
API 서버(웹사이트) 단독 진입점 — 파이프라인과 완전히 분리되어 독립 실행된다.
파이프라인(run_service.py)을 껐다 켜거나 크래시가 나도 사이트는 영향받지 않는다.
실행: python run_api.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.proc_lock import acquire

LOCK_FILE = os.path.join(os.path.dirname(__file__), "pipeline", ".api.lock")

import uvicorn

if __name__ == "__main__":
    acquire(LOCK_FILE, "API 프로세스")
    print("[API] 서버 시작: http://localhost:8000 (파이프라인과 독립 실행)")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, log_level="warning")
