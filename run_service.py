"""
창고 재고 파이프라인 서비스 진입점
실행: python run_service.py
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.scheduler import main

if __name__ == "__main__":
    main()
