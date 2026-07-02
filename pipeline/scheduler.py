import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.combining import OrTrigger

from pipeline.crawler import CrawlerPool
from pipeline.updater import FirestoreUpdater
from pipeline.snapshot import Snapshot

# stdout UTF-8 강제 (Windows 콘솔 CP949 대응)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

        # 3. Firestore diff 업데이트 + 새 스냅샷 반환
        prev = snapshot.load()
        changed, new_snap = updater.update_diff(normalized, prev)

        # 4. 매핑된 dict를 스냅샷으로 저장 (다음 비교 시 동일 형식 보장)
        snapshot.save(new_snap)

        # 수량 최종 확인: EDA 박스수 vs Firestore 박스수
        import pandas as _pd
        if not normalized.empty and "재고수량" in normalized.columns:
            eda_qty = int(_pd.to_numeric(normalized["재고수량"], errors="coerce").fillna(0).sum())
        else:
            eda_qty = 0
        fs_qty  = sum(v.get("재고", 0) or 0 for v in new_snap.values())
        qty_diff = eda_qty - fs_qty
        qty_note = f" ★ {qty_diff}박스 차이" if qty_diff != 0 else ""

        elapsed = time.time() - start
        log.info(
            f"완료 | EDA {len(normalized)}건/{eda_qty}박스 → Firestore {len(new_snap)}건/{fs_qty}박스{qty_note} | 변경 {changed}건 | {elapsed:.1f}초 소요"
        )

    except Exception as e:
        log.error(f"파이프라인 오류: {e}", exc_info=True)


def _in_operating_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # 토(5), 일(6) 제외
        return False
    return (dt.hour == 8 and dt.minute == 0) or \
           (8 < dt.hour < 17) or \
           (dt.hour == 17 and dt.minute == 0)


def main():
    log.info("=" * 50)
    log.info("창고 재고 파이프라인 서비스 시작")
    log.info("스케줄: 평일(월~금) 08:00 ~ 17:00, 1분 간격")
    log.info("=" * 50)

    scheduler = BlockingScheduler(timezone="Asia/Seoul")

    # 평일(월~금) 08:00~16:59 매분 실행 + 17:00 마지막 실행
    trigger = OrTrigger([
        CronTrigger(hour="8-16", minute="*", day_of_week="mon-fri", timezone="Asia/Seoul"),
        CronTrigger(hour="17",   minute="0", day_of_week="mon-fri", timezone="Asia/Seoul"),
    ])

    scheduler.add_job(
        run_pipeline,
        trigger,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
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

    # 운영 시간 내에 시작하면 즉시 1회 실행
    now = datetime.now()
    if _in_operating_hours(now):
        log.info(f"운영 시간 내 시작({now.strftime('%H:%M')}) - 즉시 1회 실행")
        run_pipeline()
    else:
        log.info(f"현재 시각 {now.strftime('%H:%M')} - 운영 시간(평일 08:00~17:00) 외, 다음 평일 08:00까지 대기")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("서비스 종료")
