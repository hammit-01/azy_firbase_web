"""강동2는 냉장 표시를 상품명이 아니라 규격(규격단위중량)에 "냉장EXCEL"처럼
브랜드 앞에 붙여서 줌 — 안 떼면 브랜드/평균중량 정규식이 ^로 시작을 강제해서
통째로 매칭 실패한다 (2026-08-12, 실제 라이브 데이터 "(우)부채CH/86E"/
"냉장EXCEL"에서 브랜드=NaN으로 깨지던 것 발견). 다른 창고처럼 상품명 앞으로
옮기고 규격 값에서는 뗀 뒤 브랜드/평균중량을 추출해야 한다.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_else_df import kd_eda


def _row(수탁품, 규격단위중량):
    df = pd.DataFrame([{
        "수탁품": 수탁품, "규격단위중량": 규격단위중량, "B/L NO식별번호": "TESTBL",
        "ESTNO": "86E", "재고수량": "20", "중량": "458.20",
        "유통기한제조일자": "2026.10.04", "창고": "강동2",
    }])
    df["기타정보"] = df["수탁품"].str.replace(r"[가-힣\s]", "", regex=True)
    return df


def test_brand_extracted_despite_naengjang_prefix():
    out = kd_eda(_row("(우)부채CH/86E", "냉장EXCEL"))
    assert out["브랜드"].iloc[0] == "EXCEL", out["브랜드"].iloc[0]


def test_naengjang_moved_to_product_name():
    out = kd_eda(_row("(우)부채CH/86E", "냉장EXCEL"))
    assert out["수탁품"].iloc[0] == "냉장(우)부채CH/86E"


def test_weight_extracted_when_present_after_naengjang():
    out = kd_eda(_row("목심", "냉장SADIA/BRF12.5KG"))
    assert out["브랜드"].iloc[0] == "SADIA"
    assert out["평균중량"].iloc[0] == 12.5


def test_non_naengjang_row_unaffected():
    out = kd_eda(_row("앞다리", "WINGHAM15.57KG"))
    assert out["수탁품"].iloc[0] == "앞다리"
    assert out["브랜드"].iloc[0] == "WINGHAM"
    assert out["평균중량"].iloc[0] == 15.57


if __name__ == "__main__":
    test_brand_extracted_despite_naengjang_prefix()
    test_naengjang_moved_to_product_name()
    test_weight_extracted_when_present_after_naengjang()
    test_non_naengjang_row_unaffected()
    print("OK")
