"""닭장각정육 ESTNO가 8자 이상이면 앞 7자리만 남기는지 확인 (2026-08-12,
SIF12157271 -> SIF1215 요청).
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_standard import eda_standard


def _row(estno, 수탁품="닭장각정육"):
    return pd.DataFrame([{
        "수탁품": 수탁품, "브랜드": "SEARA", "등급": "", "ESTNO": estno,
        "창고": "SWC", "재고수량": 1, "BL번호": "TESTBL", "유통기한": "",
    }])


def test_truncates_long_estno_to_7_digits():
    assert eda_standard(_row("SIF12157271"))["ESTNO"].iloc[0] == "SIF1215"
    assert eda_standard(_row("SIF12157100"))["ESTNO"].iloc[0] == "SIF1215"


def test_leaves_short_estno_alone():
    assert eda_standard(_row("SIF1215"))["ESTNO"].iloc[0] == "SIF1215"
    assert eda_standard(_row("1234567"))["ESTNO"].iloc[0] == "1234567"


def test_scoped_to_dakjang_only():
    assert eda_standard(_row("SIF12157271", 수탁품="탕갈비"))["ESTNO"].iloc[0] == "SIF12157271"


if __name__ == "__main__":
    test_truncates_long_estno_to_7_digits()
    test_leaves_short_estno_alone()
    test_scoped_to_dakjang_only()
    print("OK")
