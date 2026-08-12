"""KILCOY 양지OFF는 사내 표기로 양지ON으로 강제 변경돼야 하지만, 다른 브랜드의
양지OFF(AMH 등)는 원본 그대로 유지돼야 한다 (2026-08-12: 브랜드 조건 없이 걸려
있던 기존 규칙 때문에 AMH 양지OFF까지 같이 양지ON으로 잘못 바뀌던 버그 발견).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.mysql_db import sync_name_rename


def test_kilcoy_yangji_off_becomes_on():
    row = {"상품명": "양지OFF", "브랜드": "KILCOY", "창고": "곤지암"}
    assert sync_name_rename(row)["상품명"] == "양지ON"


def test_other_brand_yangji_off_unchanged():
    row = {"상품명": "양지OFF", "브랜드": "AMH", "창고": "곤CS"}
    assert sync_name_rename(row)["상품명"] == "양지OFF"


def test_non_gon_warehouse_unchanged():
    row = {"상품명": "양지OFF", "브랜드": "KILCOY", "창고": "SWC"}
    assert sync_name_rename(row)["상품명"] == "양지OFF"


if __name__ == "__main__":
    test_kilcoy_yangji_off_becomes_on()
    test_other_brand_yangji_off_unchanged()
    test_non_gon_warehouse_unchanged()
    print("OK")
