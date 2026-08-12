"""SWC 등급 추출 — 상위 단계(eda_common)에서 공백이 전부 제거되어 브랜드+등급이
"EXCELSEL86R5871"처럼 붙어서 들어온다(실제 기타정보 포맷). 이 상태에서
1) "SEARA"(브랜드) 안의 "SE"를 등급으로 오탐하지 않으면서
2) "EXCELSEL"의 진짜 등급 SEL은 계속 잡아야 한다.
(2026-08-12, 단순 단어경계 앵커만 걸었을 때 SEARA는 고쳤지만 EXCEL/SEL,
KILCOY/GF, TONNIES/PRE 등 정상 등급까지 같이 사라지는 회귀가 실제 운영 데이터로
확인되어, 아는 브랜드를 먼저 잘라내는 방식으로 재수정.)
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_added import swc


def _row(기타정보):
    # 실제 파이프라인에서 eda_common이 수탁품의 한글/공백을 전부 제거한 뒤
    # swc()로 넘기므로, 여기서도 공백 없이 브랜드+등급+숫자가 붙은 형태로 준다.
    return pd.DataFrame([{"규격단위중량": "12.00KG", "기타정보": 기타정보}])


def test_se_not_matched_inside_searah():
    df = swc(_row("SEARASIF12157271[000000  ]"))
    assert pd.isna(df["등급"].iloc[0]), df["등급"].iloc[0]
    assert df["브랜드"].iloc[0] == "SEARA"


def test_sel_survives_when_glued_to_brand():
    df = swc(_row("EXCELSEL86R5871[000000  ]"))
    assert df["등급"].iloc[0] == "SEL", df["등급"].iloc[0]


def test_other_grades_glued_to_brand_still_match():
    assert swc(_row("EXCELCH86R1500[000000  ]"))["등급"].iloc[0] == "CH"
    assert swc(_row("KILCOYGF640891592[000014  ]"))["등급"].iloc[0] == "GF"
    assert swc(_row("TONNIESPRE20202EG5241[000000  ]"))["등급"].iloc[0] == "PRE"


def test_no_grade_token_stays_empty():
    assert pd.isna(swc(_row("EXCEL86R9900[000000  ]"))["등급"].iloc[0])
    assert pd.isna(swc(_row("TONNIES688EG3500[000000  ]"))["등급"].iloc[0])


if __name__ == "__main__":
    test_se_not_matched_inside_searah()
    test_sel_survives_when_glued_to_brand()
    test_other_grades_glued_to_brand_still_match()
    test_no_grade_token_stays_empty()
    print("OK")
