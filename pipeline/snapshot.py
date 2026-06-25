import pickle
import logging
from pathlib import Path

log = logging.getLogger("snapshot")


class Snapshot:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            log.info("스냅샷 없음 - 첫 실행 (전체 쓰기)")
            return {}
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            log.info(f"스냅샷 복구: {len(data)}건")
            return data
        except Exception as e:
            log.warning(f"스냅샷 로드 실패 ({e}) - 전체 쓰기로 진행")
            return {}

    def save(self, mapped_dict: dict):
        """updater가 반환한 매핑된 dict를 그대로 저장"""
        try:
            with open(self.path, "wb") as f:
                pickle.dump(mapped_dict, f)
        except Exception as e:
            log.warning(f"스냅샷 저장 실패: {e}")
