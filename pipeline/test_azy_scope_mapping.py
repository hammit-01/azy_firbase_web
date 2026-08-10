"""SITE_TO_WAREHOUSE_NAME(scheduler.py)이 여전히 유효한 크롤러 사이트키를 가리키는지 확인.
크롤링 사이트 목록(PROCESS_MAP)이 바뀌었는데 이 매핑을 안 고치면, 재고가 빠진
상품 행이 영원히 안 지워지는 사고가 조용히 재발한다(2026-08-10 프라자 사고 참고).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.crawling_list import PROCESS_MAP
from pipeline.scheduler import SITE_TO_WAREHOUSE_NAME


def test_site_keys_still_exist():
    for site_key in SITE_TO_WAREHOUSE_NAME:
        assert site_key in PROCESS_MAP, f"{site_key}가 PROCESS_MAP에서 사라짐 — SITE_TO_WAREHOUSE_NAME 갱신 필요"


if __name__ == "__main__":
    test_site_keys_still_exist()
    print("OK")
