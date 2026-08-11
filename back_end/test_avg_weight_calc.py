"""CH/프라자/한라곤지암/한라동탄 평균중량 = 중량(소수점 2자리) / 재고수량 계산 확인.
(2026-08-11, 규격단위중량 파싱 방식에서 실측 중량 기준으로 변경)
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_ch_plz_cs import ch_eda, plz_eda
from back_end.eda_else_df import hl_eda


def _base_row(**overrides):
    row = {
        "수탁품": "테스트품목", "규격단위중량": "", "B/L NO식별번호": "TESTBL",
        "ESTNO": "", "재고수량": "10", "중량": "123.456", "유통기한제조일자": "",
        "창고": "", "기타정보": "UN/123-EXCEL",
    }
    row.update(overrides)
    return row


def test_ch_avg_weight():
    df = pd.DataFrame([_base_row()])
    result = ch_eda(df)
    assert result["평균중량"].iloc[0] == round(123.46 / 10, 2)


def test_plz_avg_weight():
    df = pd.DataFrame([_base_row(규격단위중량="SWIFT123KG")])
    result = plz_eda(df)
    assert result["평균중량"].iloc[0] == round(123.46 / 10, 2)


def test_hl_avg_weight():
    df = pd.DataFrame([_base_row()])
    result = hl_eda(df)
    assert result["평균중량"].iloc[0] == round(123.46 / 10, 2)


if __name__ == "__main__":
    test_ch_avg_weight()
    test_plz_avg_weight()
    test_hl_avg_weight()
    print("OK")
