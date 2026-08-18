"""로컬 전용 테스트 API 서버 — 8001번 포트, 이 dev 폴더의 파일을 서빙한다.
Cloudflare 터널은 8000번만 내보내므로 이 포트는 외부에 노출되지 않는다.
DB는 prod와 동일(MYSQL_* 환경변수 공유)이라 실제 데이터로 UI를 확인할 수 있다.
실행: python run_api_test.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn

if __name__ == "__main__":
    print("[TEST API] 서버 시작: http://localhost:8001/warehouse_main.html (로컬 전용, 외부 비노출)")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8001, log_level="warning")
