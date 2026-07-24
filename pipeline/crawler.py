import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from back_end.crawling_list import login, get_data, get_users, PROCESS_MAP, USER_AGENT
from back_end.back_eda_main import list_eda

log = logging.getLogger("crawler")

WAREHOUSE_XLSX = "back_end/data/warehouse_list.xlsx"
TIMEOUT_SEC    = 120  # 창고 수 증가로 여유 확보


def _load_active_warehouses() -> pd.DataFrame:
    df = pd.read_excel(WAREHOUSE_XLSX)
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df["ip포트"] = df["ip포트"].astype(str).str.strip()

    # ip포트가 있는 모든 창고 활성화 (NaN 제외)
    active = df[df["ip포트"].notna() & (df["ip포트"] != "nan") & (df["ip포트"] != "")]
    return active


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _crawl_single_row(row: pd.Series, session_cache: dict, cache_lock: threading.Lock) -> tuple:
    warehouse = str(row["창고"])
    ip_port   = str(row["ip포트"])
    path      = str(row["약식주소"])
    frames    = []

    users = get_users(row)
    if warehouse == "대재":
        # 일반/웹출고/웹출고(통관분) 3계정이 전부 동일한 전체 재고를 반환 → 뒤 단계의
        # pk 합산 로직이 이를 서로 다른 로트로 오인해 3배로 집계됨(2026-07-21, 2307→6921박스).
        # 세 계정 데이터가 같다고 확인돼서 일반 계정 하나만 쓰도록 제한.
        users = [u for u in users if u[0] == "일반"]

    for user_type, uid, pw, scustcd, scmdept in users:
        cache_key = (warehouse, user_type)
        try:
            with cache_lock:
                session = session_cache.get(cache_key)

            data = None
            if session is not None:
                # 캐시된 세션으로 우선 시도 — 유효하면 재로그인 없이 바로 조회
                data = get_data(session, ip_port, path, scustcd, scmdept, warehouse)

            if session is None or data is None:
                # 세션 없음/만료 → 재로그인 후 캐시 갱신
                session = _new_session()
                res = login(session, ip_port, path, uid, pw, warehouse)
                if res is None:
                    with cache_lock:
                        session_cache.pop(cache_key, None)
                    continue
                with cache_lock:
                    session_cache[cache_key] = session
                data = get_data(session, ip_port, path, scustcd, scmdept, warehouse)

            if data is None or data.empty:
                continue

            # drop_duplicates() 금지: 동일 BL/수량/유통기한이라도 별도 로트인 경우가 있음
            # (#012와 동일한 유형의 버그 — 뒤 단계의 pk/uid 기준 groupby+합산이 중복을 처리하므로
            # 여기서 행 단위로 먼저 지우면 유효한 박스 수량이 조용히 손실된다)
            data["창고"] = warehouse

            func = PROCESS_MAP.get(warehouse)
            if func:
                data = func(data)

            if data is not None and not data.empty:
                frames.append(data)

        except Exception as e:
            with cache_lock:
                session_cache.pop(cache_key, None)
            log.error(f"  [{warehouse}] {user_type} 오류: {e}")

    return warehouse, pd.concat(frames, ignore_index=True) if frames else None


class CrawlerPool:
    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers
        # (창고, 계정유형) → 로그인된 requests.Session — 사이클 간 재사용, 만료 시에만 재로그인
        self._session_cache: dict = {}
        self._cache_lock = threading.Lock()

    def crawl_all(self, exclude: list = None) -> dict:
        """활성 창고를 병렬 크롤링. exclude에 담긴 창고명은 제외(독립 스케줄 창고용).
        반환: {창고명: DataFrame | None}"""
        active = _load_active_warehouses()
        if exclude:
            active = active[~active["창고"].isin(exclude)]
        rows   = list(active.iterrows())
        results = {}

        workers = min(self.max_workers, len(rows)) if rows else 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_crawl_single_row, row, self._session_cache, self._cache_lock): row["창고"]
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

    def crawl_one(self, warehouse_name: str):
        """창고 하나만 단독 크롤링 (JNS처럼 다른 창고와 독립된 스케줄로 도는 경우용).
        반환: DataFrame | None"""
        active = _load_active_warehouses()
        match = active[active["창고"] == warehouse_name]
        if match.empty:
            log.error(f"  ✗ {warehouse_name}: 활성 창고 목록에 없음")
            return None
        try:
            name, df = _crawl_single_row(match.iloc[0], self._session_cache, self._cache_lock)
            cnt = len(df) if df is not None else 0
            log.info(f"  ✓ {name}: {cnt}건")
            return df
        except Exception as e:
            log.error(f"  ✗ {warehouse_name}: {e}")
            return None

    @staticmethod
    def normalize(results: dict) -> tuple:
        """크롤링 결과를 EDA 정규화. inventory용(JNS)과 azy_inventory용(나머지) 분리 반환."""
        success = {w: df for w, df in results.items() if df is not None and not df.empty}

        jns_df   = success.get("제니스(곤지암)", pd.DataFrame())
        others   = [df for w, df in success.items() if w != "제니스(곤지암)"]
        final_df = pd.concat(others, ignore_index=True) if others else pd.DataFrame()

        raw_qty = 0
        if not jns_df.empty and "재고수량" in jns_df.columns:
            raw_qty = int(pd.to_numeric(
                jns_df["재고수량"].astype(str).str.replace(",", "", regex=False),
                errors="coerce"
            ).fillna(0).sum())
            log.info(f"  [정규화 전] 원본: {len(jns_df)}행 / {raw_qty}박스")

        _, normalized, azy_normalized = list_eda(final_df, jns_df)

        if not normalized.empty and "재고수량" in normalized.columns:
            eda_qty = int(pd.to_numeric(normalized["재고수량"], errors="coerce").fillna(0).sum())
            log.info(f"  [정규화 후] EDA: {len(normalized)}행 / {eda_qty}박스")
            if raw_qty and raw_qty != eda_qty:
                log.warning(f"  [정규화 경고] 박스 수 변동: {raw_qty} → {eda_qty} ({eda_qty - raw_qty:+d}박스)")

        if not azy_normalized.empty:
            log.info(f"  [azy] {len(azy_normalized)}건")

        return normalized, azy_normalized
