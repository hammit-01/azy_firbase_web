import logging
import signal
import sys
import time
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pipeline.crawler import CrawlerPool
from pipeline.updater import FirestoreUpdater
from pipeline.snapshot import Snapshot

# ── 로깅 설정 ───────────────────────────────────────────
LOG_DIR = Path("pipeline/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")

# ── 컴포넌트 싱글턴 ─────────────────────────────────────
snapshot = Snapshot(Path("pipeline/snapshot.pkl"))
updater  = FirestoreUpdater()
crawler  = CrawlerPool(max_workers=20)


def run_pipeline():
    start = time.time()
    log.info("─" * 50)
    log.info("파이프라인 시작")

    try:
        # 1. 병렬 크롤링
        results = crawler.crawl_all()

        failed = [w for w, df in results.items() if df is None or (hasattr(df, "empty") and df.empty)]
        if failed:
            log.warning(f"실패 창고: {', '.join(failed)}")

        # 2. 정규화
        normalized = crawler.normalize(results)
        if normalized.empty:
            log.warning("정규화 후 데이터 없음 - 이번 라운드 스킵")
            return

        # 3. Firestore diff 업데이트
        prev = snapshot.load()
        changed = updater.update_diff(normalized, prev)

        # 4. 스냅샷 저장
        snapshot.save(normalized)

        elapsed = time.time() - start
        log.info(
            f"완료 | 총 {len(normalized)}건 조회 | 변경 {changed}건 | {elapsed:.1f}초 소요"
        )

    except Exception as e:
        log.error(f"파이프라인 오류: {e}", exc_info=True)


def main():
    log.info("=" * 50)
    log.info("창고 재고 파이프라인 서비스 시작")
    log.info("=" * 50)

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_pipeline,
        IntervalTrigger(minutes=1),
        max_instances=1,         # 이전 실행 중이면 새 실행 스킵
        coalesce=True,           # 밀린 실행은 1번만
        misfire_grace_time=30,   # 30초 내 지연은 허용
        id="warehouse_pipeline",
    )

    def _shutdown(signum, frame):
        log.info("종료 신호 수신 - 스케줄러 중지")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    # SIGTERM: Linux/NSSM 지원, Windows 환경에 따라 다를 수 있음
    try:
        signal.signal(signal.SIGTERM, _shutdown)
    except (OSError, ValueError):
        pass

    # 시작 즉시 한 번 실행 후 주기 시작
    log.info("즉시 실행 후 1분 주기 시작")
    run_pipeline()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("서비스 종료")
