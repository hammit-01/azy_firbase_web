"""KILCOY 양지OFF는 사내에서 양지ON으로 부름(2026-08-12 요청). 다른 브랜드의
양지OFF(AMH 등)는 원본 표기 그대로 유지해야 함.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.replace_name import replace_name


def _row(수탁품, 브랜드):
    return pd.DataFrame([{
        "수탁품": 수탁품, "브랜드": 브랜드, "등급": "S", "ESTNO": "1",
        "창고": "곤지암", "재고수량": 1, "BL번호": "TESTBL", "유통기한": "",
    }])


def test_kilcoy_yangji_off_becomes_on():
    df = replace_name(_row("양지OFF", "KILCOY"))
    assert df["수탁품"].iloc[0] == "양지ON"


def test_other_brand_yangji_off_unchanged():
    df = replace_name(_row("양지OFF", "AMH"))
    assert df["수탁품"].iloc[0] == "양지OFF"


if __name__ == "__main__":
    test_kilcoy_yangji_off_becomes_on()
    test_other_brand_yangji_off_unchanged()
    print("OK")
