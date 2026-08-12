"""척갈비/KILCOY ESTNO가 전부 숫자면 앞 3자리만 남기는지 확인
(2026-08-12, 6402->640, 6401->640 요청).
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_standard import eda_standard


def _row(estno, 브랜드="KILCOY", 수탁품="척갈비"):
    return pd.DataFrame([{
        "수탁품": 수탁품, "브랜드": 브랜드, "등급": "CH", "ESTNO": estno,
        "창고": "X", "재고수량": 1, "BL번호": "TESTBL", "유통기한": "",
    }])


def test_truncates_numeric_estno_to_3_digits():
    assert eda_standard(_row("6402"))["ESTNO"].iloc[0] == "640"
    assert eda_standard(_row("6401"))["ESTNO"].iloc[0] == "640"
    assert eda_standard(_row("640"))["ESTNO"].iloc[0] == "640"


def test_leaves_non_numeric_estno_alone():
    assert eda_standard(_row("3D"))["ESTNO"].iloc[0] == "3D"


def test_scoped_to_kilcoy_chuck_only():
    assert eda_standard(_row("6402", 브랜드="IBP"))["ESTNO"].iloc[0] == "6402"
    assert eda_standard(_row("6402", 수탁품="소갈비"))["ESTNO"].iloc[0] == "6402"


if __name__ == "__main__":
    test_truncates_numeric_estno_to_3_digits()
    test_leaves_non_numeric_estno_alone()
    test_scoped_to_kilcoy_chuck_only()
    print("OK")
