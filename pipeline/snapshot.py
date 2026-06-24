import pickle
import logging
import pandas as pd
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

    def save(self, df: pd.DataFrame):
        try:
            data = self._df_to_dict(df)
            with open(self.path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            log.warning(f"스냅샷 저장 실패: {e}")

    @staticmethod
    def _df_to_dict(df: pd.DataFrame) -> dict:
        result = {}
        for _, row in df.iterrows():
            pk = str(row.get("pk", ""))
            if not pk:
                continue
            result[pk] = {
                k: (None if pd.isna(v) else v)
                for k, v in row.to_dict().items()
            }
        return result
