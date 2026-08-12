"""JNS(곤) 상품명 괄호 처리 — (PCS), (MEATY)처럼 상품명 일부인 괄호는 등급으로
오인해 잘라내면 안 됨 (2026-08-12, 삼겹양지(PCS)/조각탕갈비(MEATY)가 매 사이클
괄호 잘려나가던 버그 발견). 반면 소갈비(T)처럼 진짜 등급-in-parens는 계속
분리돼야 함.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_standard import eda_standard


def _row(수탁품, 등급="", 창고="곤지암"):
    return pd.DataFrame([{
        "수탁품": 수탁품, "브랜드": "X", "등급": 등급, "ESTNO": "1",
        "창고": 창고, "재고수량": 1, "BL번호": "TESTBL", "유통기한": "",
    }])


def test_pcs_suffix_preserved():
    df = eda_standard(_row("삼겹양지(PCS)"))
    assert df["수탁품"].iloc[0] == "삼겹양지(PCS)", df["수탁품"].iloc[0]


def test_meaty_suffix_preserved():
    df = eda_standard(_row("조각탕갈비(MEATY)"))
    assert df["수탁품"].iloc[0] == "조각탕갈비(MEATY)", df["수탁품"].iloc[0]


def test_genuine_grade_in_parens_still_split():
    df = eda_standard(_row("소갈비(T)"))
    assert df["수탁품"].iloc[0] == "소갈비", df["수탁품"].iloc[0]
    assert df["등급"].iloc[0] == "T"


if __name__ == "__main__":
    test_pcs_suffix_preserved()
    test_meaty_suffix_preserved()
    test_genuine_grade_in_parens_still_split()
    print("OK")
