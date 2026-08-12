"""SWC 등급 추출이 "SE"를 브랜드 "SEARA" 안의 부분 문자열로 오탐하지 않는지
확인 (2026-08-12, 닭장각정육/SEARA에 없는 등급 SE가 잡히던 버그 수정).
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.eda_added import swc


def _row(기타정보):
    return pd.DataFrame([{"규격단위중량": "12.00KG", "기타정보": 기타정보}])


def test_se_not_matched_inside_searah():
    df = swc(_row("닭장각정육 SEARA SIF1215 7271[000000  ]"))
    assert pd.isna(df["등급"].iloc[0]), df["등급"].iloc[0]


def test_genuine_se_grade_still_matches():
    df = swc(_row("소갈비 EXCEL SE 86R[000000  ]"))
    assert df["등급"].iloc[0] == "SE"


def test_sel_still_matches_over_se():
    df = swc(_row("탕갈비 EXCEL SEL86R[000000  ]"))
    assert df["등급"].iloc[0] == "SEL"


def test_other_grades_unaffected():
    assert swc(_row("사태(뒤) KILCOY GF640[000000  ]"))["등급"].iloc[0] == "GF"
    assert swc(_row("삼겹 TONNIES PRE20202EG[000000  ]"))["등급"].iloc[0] == "PRE"


if __name__ == "__main__":
    test_se_not_matched_inside_searah()
    test_genuine_se_grade_still_matches()
    test_sel_still_matches_over_se()
    test_other_grades_unaffected()
    print("OK")
