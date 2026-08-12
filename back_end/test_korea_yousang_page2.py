"""고려/유상 재고 소스를 재고현황(1)에서 (2)로 교체(2026-08-12) — (1)은 기준일자가
"당일"이 아니라 "8/1~오늘" 기간 조회라 실제 현재고와 안 맞음(사용자 확인). (2)는
컬럼 배치가 (1)과 달라 인덱스 리매핑도 같이 검증한다(라이브 데이터로 BL 교차검증한
실제 값 사용).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end import crawling_handmade as ch

_KOREA_P2_ROW = [
    "1", "대창(8788610)ACC", "16K", "", "125", "2,000.00", "2026-04-20", "(288)",
    "AUBNE0114271", "통관", "2026-06-16", "0", "ACC", "호주", "1620",
    "2025-12-22", "2027-12-21", "496", "", "801079501270", "801079501270", "",
]

_YOUSANG_P2_ROW = [
    "1", "우갈비A E.239(카지노)(909618-4)", "약 15.2kg", "C/T", "34", "0.00",
    "2026-05-08", "92", "HLCUSYD260342701", "통관", "2026-06-26", "0", "카지노",
    "호주", "", "2026-02-04", "2028-02-03", "540", "", "", "HLBU909618-4", "",
]


def test_korea_eda_uses_page2_column_layout():
    with patch.object(ch, "_ecms_fetch_cached", return_value=[_KOREA_P2_ROW]):
        df = ch.korea_eda()
    assert df.loc[0, "BL번호"] == "AUBNE0114271"
    assert df.loc[0, "재고수량"] == "125"
    assert df.loc[0, "유통기한"] == "2027-12-21"
    assert df.loc[0, "브랜드"] == "ACC"
    assert df.loc[0, "ESTNO"] == "1620"


def test_korea_eda_requests_page2_url():
    with patch.object(ch, "_ecms_fetch_cached", return_value=[_KOREA_P2_ROW]) as mocked:
        ch.korea_eda()
    _, kwargs_or_args = mocked.call_args, mocked.call_args
    called_urls = mocked.call_args[0]
    assert any("instockpage2prime" in str(a) for a in called_urls)


def test_yousang_eda_uses_page2_column_layout():
    with patch.object(ch, "_ecms_fetch_cached", return_value=[_YOUSANG_P2_ROW]):
        df = ch.yousang_eda()
    assert df.loc[0, "BL번호"] == "HLCUSYD260342701"
    assert df.loc[0, "재고수량"] == "34"
    assert df.loc[0, "유통기한"] == "2028-02-03"
    assert df.loc[0, "브랜드"] == "카지노"


if __name__ == "__main__":
    test_korea_eda_uses_page2_column_layout()
    test_korea_eda_requests_page2_url()
    test_yousang_eda_uses_page2_column_layout()
    print("OK")
