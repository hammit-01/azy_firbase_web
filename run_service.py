"""
창고 재고 파이프라인 서비스 진입점 (크롤링/EDA/DB 업데이트 전용).
API 서버(웹사이트)는 run_api.py로 완전히 분리된 별도 프로세스에서 실행된다 —
파이프라인을 껐다 켜도 사이트는 계속 살아있어야 하기 때문.
실행: python run_service.py
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.proc_lock import acquire

LOCK_FILE = os.path.join(os.path.dirname(__file__), "pipeline", ".service.lock")

from pipeline.scheduler import main

if __name__ == "__main__":
    acquire(LOCK_FILE, "파이프라인 프로세스")
    main()
