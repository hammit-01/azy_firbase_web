"""소갈비/SWIFT/3D(+한라곤지암 탕갈비(MEATY) 파생) 등급 하드코딩이 등급 빈값일
때만 걸리고, 원본에 실제 등급이 있으면 존중하는지 확인 (2026-08-11, 무조건
덮어쓰던 것에서 조건부로 변경).
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_standard import eda_standard
from back_end.replace_name import replace_name


def _row(**overrides):
    row = {
        "수탁품": "소갈비", "브랜드": "SWIFT", "등급": "", "ESTNO": "3D",
        "창고": "한라곤지암", "재고수량": 1, "BL번호": "TESTBL", "유통기한": "",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_eda_standard_fills_only_when_empty():
    filled = eda_standard(_row(등급=""))
    assert filled["등급"].iloc[0] == "UN"

    preserved = eda_standard(_row(등급="CH"))
    assert preserved["등급"].iloc[0] == "CH"


def test_eda_standard_fills_when_nan():
    # 2026-08-12 실제 재현: 등급이 문자열 ""이 아니라 진짜 NaN인 경우(삼진2
    # MAEU266114518) — .astype(str)로는 안 잡혀서 규칙이 하나도 안 걸리던 버그.
    filled = eda_standard(_row(등급=pd.NA))
    assert filled["등급"].iloc[0] == "UN"


def test_replace_name_hanla_rule_fills_only_when_empty():
    filled = replace_name(_row(등급=""))
    assert filled["수탁품"].iloc[0] == "탕갈비(MEATY)"
    assert filled["등급"].iloc[0] == "UN"

    preserved = replace_name(_row(등급="CH"))
    assert preserved["수탁품"].iloc[0] == "소갈비"  # 등급 있으면 상품명도 안 바뀜
    assert preserved["등급"].iloc[0] == "CH"


def test_replace_name_hanla_rule_fills_when_nan():
    filled = replace_name(_row(등급=pd.NA))
    assert filled["수탁품"].iloc[0] == "탕갈비(MEATY)"
    assert filled["등급"].iloc[0] == "UN"


if __name__ == "__main__":
    test_eda_standard_fills_only_when_empty()
    test_eda_standard_fills_when_nan()
    test_replace_name_hanla_rule_fills_only_when_empty()
    test_replace_name_hanla_rule_fills_when_nan()
    print("OK")
