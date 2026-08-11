"""에이스 평균중량이 원본 표 12번째 칸(index 11, 사이트가 이미 계산해둔 값)에서
오는지 확인 — 기존엔 항상 빈 값으로 고정돼있었음(2026-08-11 발견, 실제 크롤
결과로 384.00÷32=12.00 등 일치 확인 후 수정).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from back_end.crawling_handmade import _ace_records_to_df


def test_avg_weight_from_index_11():
    records = [
        ["AURORA)닭정육", "26361169", "규격/유송", "BOX", "x", "EGLV360500166386",
         "", "SIF3125", "A30302", "32", "384.00", "12.00", "2027-10-13", "통관", "브라질", ""],
        ["CREEKSTONE)우일반갈비", "26379814", "평중", "BOX", "x", "HDMUDALA32081400",
         "803056400747", "27", "A20302", "49", "1,358.28", "27.72", "2027-11-20", "통관", "미국", ""],
    ]
    df = _ace_records_to_df(records, "에이스기흥")
    assert list(df["평균중량"]) == ["12.00", "27.72"]


if __name__ == "__main__":
    test_avg_weight_from_index_11()
    print("OK")
