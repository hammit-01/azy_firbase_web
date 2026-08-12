"""azy_inventory 행 id(_azy_uid) — 같은 BL/ESTNO/등급/상품명/창고라도 특이품
(파손/상이품/반품/검품) 사유가 다르면 별도 id로 갈라져야 한다 (2026-08-12,
ONEYRICFPX299900: 정상 2178박스 + 파손 1박스가 같은 uid로 합쳐지면서 정상
재고까지 통째로 "특이품"으로 잘못 태깅되던 버그 발견). qualifier가 없는 절대
다수 케이스는 기존 id 형식이 그대로 유지돼야 한다(안 그러면 전체 행 id가
바뀌어서 테이블 전체가 삭제+재삽입된다).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.scheduler import _azy_uid


def test_normal_row_keeps_legacy_id_format():
    uid = _azy_uid("ONEYRICFPX299900", "86R", "", "우건", "SWC")
    assert uid == "ONEYRICFPX299900_86R__우건_SWC", uid


def test_damaged_lot_gets_distinct_id_from_normal_lot():
    normal = _azy_uid("ONEYRICFPX299900", "86R", "", "우건", "SWC")
    damaged = _azy_uid("ONEYRICFPX299900", "86R", "", "우건", "SWC", "특이품", "파손")
    assert normal != damaged
    assert damaged == "ONEYRICFPX299900_86R__우건_SWC_파손"


def test_no_bl_returns_none():
    assert _azy_uid("", "86R", "", "우건", "SWC") is None


if __name__ == "__main__":
    test_normal_row_keeps_legacy_id_format()
    test_damaged_lot_gets_distinct_id_from_normal_lot()
    test_no_bl_returns_none()
    print("OK")
