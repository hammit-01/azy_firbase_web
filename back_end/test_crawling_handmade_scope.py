"""crawling_handmade()가 창고별 성공/실패를 정확히 구분해서 반환하는지 확인.
실패(None)와 진짜 빈 재고([]→빈 DataFrame)를 못 구분하면, 실패한 창고가
stale 삭제 scope에 들어가 진짜 재고가 삭제되는 사고로 이어진다(2026-08-11 참고).
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end import crawling_handmade as ch


def _row(창고):
    return pd.DataFrame([{"수탁품": "테스트품목", "평균중량": "1KG", "재고수량": 1,
                           "BL번호": "TESTBL", "유통기한": "", "브랜드": "", "창고": 창고}])


def test_failed_warehouse_excluded_from_succeeded(monkeypatch):
    monkeypatch.setattr(ch, "korea_eda", lambda: None)                 # 크롤 실패
    monkeypatch.setattr(ch, "yousang_eda", lambda: pd.DataFrame())      # 성공, 진짜 0건
    monkeypatch.setattr(ch, "kyunu_eda", lambda: _row("견우오아시스"))  # 성공, 데이터 있음
    monkeypatch.setattr(ch, "mibing_eda", lambda: None)                 # 크롤 실패

    df, succeeded = ch.crawling_handmade()

    assert succeeded == {"유상", "견우오아시스"}, succeeded
    assert "고려" not in succeeded and "미빙냉장" not in succeeded
    assert list(df["창고"]) == ["견우오아시스"]


if __name__ == "__main__":
    import types
    # pytest 없이도 돌아가게 monkeypatch를 간단히 흉내
    class _MP:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)
    test_failed_warehouse_excluded_from_succeeded(_MP())
    print("OK")
