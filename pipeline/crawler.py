import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from back_end.crawling_list import login, get_data, get_users, PROCESS_MAP
from back_end.back_eda_main import list_eda

log = logging.getLogger("crawler")

WAREHOUSE_XLSX = "back_end/data/warehouse_list.xlsx"
TIMEOUT_SEC    = 50   # 1분 주기이므로 50초 타임아웃


def _load_active_warehouses() -> pd.DataFrame:
    df = pd.read_excel(WAREHOUSE_XLSX)
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df["ip포트"] = df["ip포트"].astype(str).str.strip()

    # ── 활성 창고 필터 ──────────────────────────────────
    # 현재: 제니스(곤지암)만 활성
    # 추후 창고 추가 시 아래 주석을 해제하거나 조건을 수정하세요
    active = df[df["창고"] == "제니스(곤지암)"]

    # 전체 활성화 예시:
    # active = df  # 모든 창고

    return active


def _crawl_single_row(row: pd.Series) -> tuple:
    warehouse = str(row["창고"])
    ip_port   = str(row["ip포트"])
    path      = str(row["약식주소"])
    frames    = []

    for user_type, uid, pw, scustcd, scmdept in get_users(row):
        session = requests.Session()
        try:
            res = login(session, ip_port, path, uid, pw, warehouse)
            if res is None:
                continue

            data = get_data(session, ip_port, path, scustcd, scmdept, warehouse)
            if data is None or data.empty:
                continue

            data = data.drop_duplicates()
            data["창고"] = warehouse

            func = PROCESS_MAP.get(warehouse)
            if func:
                data = func(data)

            if data is not None and not data.empty:
                frames.append(data)

        except Exception as e:
            log.error(f"  [{warehouse}] {user_type} 오류: {e}")

    return warehouse, pd.concat(frames, ignore_index=True) if frames else None


class CrawlerPool:
    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers

    def crawl_all(self) -> dict:
        """모든 활성 창고를 병렬 크롤링. 반환: {창고명: DataFrame | None}"""
        active = _load_active_warehouses()
        rows   = list(active.iterrows())
        results = {}

        workers = min(self.max_workers, len(rows)) if rows else 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_crawl_single_row, row): row["창고"]
                for _, row in rows
            }
            for future in as_completed(futures, timeout=TIMEOUT_SEC):
                warehouse = futures[future]
                try:
                    name, df = future.result()
                    results[name] = df
                    cnt = len(df) if df is not None else 0
                    log.info(f"  ✓ {name}: {cnt}건")
                except Exception as e:
                    results[warehouse] = None
                    log.error(f"  ✗ {warehouse}: {e}")

        return results

    @staticmethod
    def normalize(results: dict) -> pd.DataFrame:
        """크롤링 결과를 EDA 정규화. 기존 back_eda_main.list_eda 활용."""
        success = {w: df for w, df in results.items() if df is not None and not df.empty}
        if not success:
            return pd.DataFrame()

        jns_df  = success.get("제니스(곤지암)", pd.DataFrame())
        others  = [df for w, df in success.items() if w != "제니스(곤지암)"]
        final_df = pd.concat(others, ignore_index=True) if others else pd.DataFrame()

        # 원본 수량 로그
        if not jns_df.empty and "재고수량" in jns_df.columns:
            raw_qty = pd.to_numeric(
                jns_df["재고수량"].astype(str).str.replace(",", "", regex=False),
                errors="coerce"
            ).fillna(0).sum()
            log.info(f"  [정규화 전] 원본: {len(jns_df)}행 / {int(raw_qty)}박스")

        _, normalized = list_eda(final_df, jns_df)
        # list_eda 내부에서 pk 기준 중복 합산 처리됨 (drop_duplicates 불필요)

        if not normalized.empty and "재고수량" in normalized.columns:
            eda_qty = pd.to_numeric(normalized["재고수량"], errors="coerce").fillna(0).sum()
            log.info(f"  [정규화 후] EDA: {len(normalized)}행 / {int(eda_qty)}박스")

        return normalized
