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
from pipeline.mysql_updater import MySQLUpdater
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

# ── 에이스냉장 전용 로거 (동시접속 1명 제한 — 별도 정각 스케줄) ──
# propagate=False로 메인 pipeline.log에는 섞이지 않고 pipeline_ace.log에만 기록
ace_log = logging.getLogger("ace_scheduler")
ace_log.setLevel(logging.INFO)
ace_log.propagate = False
_ace_handler = logging.FileHandler(LOG_DIR / "pipeline_ace.log", encoding="utf-8")
_ace_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
ace_log.addHandler(_ace_handler)

# ── JNS(제니스) 전용 로거 — 나머지 창고 사이클과 완전히 독립 실행 ──
jns_log = logging.getLogger("jns_scheduler")
jns_log.setLevel(logging.INFO)
jns_log.propagate = False
_jns_handler = logging.FileHandler(LOG_DIR / "pipeline_jns.log", encoding="utf-8")
_jns_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
jns_log.addHandler(_jns_handler)

JNS_WAREHOUSE = "제니스(곤지암)"

# ── 컴포넌트 싱글턴 ─────────────────────────────────────
snapshot = Snapshot(Path("pipeline/snapshot.pkl"))
updater  = MySQLUpdater()
crawler  = CrawlerPool(max_workers=20)


def _upload_azy(azy_df, warehouse_scope=None):
    """azy_inventory 테이블 diff 갱신 — 기존 행의 홀딩/상태/메모는 보존.

    warehouse_scope: 지정하면 그 창고들에 속한 기존 행만 대상으로 stale 삭제 판단.
    (예: 에이스 전용 잡이 azy_data 전체가 아니라 에이스 3개 창고만 넘길 때,
    다른 창고 행까지 stale로 오인해 삭제하는 걸 방지)
    """
    import uuid, math
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pipeline.mysql_db import (
        get_conn, upsert_azy_inventory, delete_azy_inventory, get_azy_holding_sum,
    )

    if azy_df is None or azy_df.empty:
        return

    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

    def _s(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(v)

    with get_conn() as conn:
        holding_sum = get_azy_holding_sum(conn)

    rows = {}
    for _, r in azy_df.iterrows():
        bl    = _s(r.get("BL번호"))
        estno = _s(r.get("ESTNO") or r.get("식별번호", ""))
        grade = _s(r.get("등급"))
        wh    = _s(r.get("창고"))
        # 등급도 식별자에 포함 — 같은 BL+ESTNO라도 등급(CH/UN 등)이 다르면
        # 별도 재고이므로 로트/저장위치 중복 합산 대상이 아님
        uid   = f"{bl}_{estno}_{grade}_{wh}" if bl else uuid.uuid4().hex
        try:
            raw_qty = int(str(r.get("재고수량", 0)).replace(",", ""))
        except Exception:
            raw_qty = 0
        if raw_qty <= 0:
            continue
        h_qty = holding_sum.get(uid, 0)
        qty   = raw_qty - h_qty
        if qty <= 0:
            continue
        try:
            avg_w = float(r.get("평균중량") or r.get("평중", None))
            if math.isnan(avg_w):
                avg_w = None
        except Exception:
            avg_w = None
        if uid in rows:
            # 같은 BL+ESTNO+창고로 로트/저장위치만 다른 중복 — 합산
            rows[uid]["재고"] += qty
            rows[uid]["원본재고"] += raw_qty
            rows[uid]["holdingTotal"] += h_qty
            continue

        rows[uid] = {
            "id": uid, "pk": "",
            "상품명": _s(r.get("수탁품")),
            "브랜드": _s(r.get("브랜드")),
            "등급":   _s(r.get("등급")),
            "ESTNO":  estno,
            "재고":   qty,
            "BL":     bl,
            "창고":   wh,
            "유통기한": _s(r.get("유통기한")),
            "중량": None, "평중": avg_w,
            "출고일": "",
            "수집일": today,
            "holdingTotal": h_qty, "holdingRecordId": "", "이상": "",
            "원본재고": raw_qty,
        }

    # stale 삭제 범위 — 명시 안 하면 이번에 실제로 크롤링된 창고들로 자동 한정
    # (예: 이 잡이 에이스만 넘기면 에이스 창고만, 메인 잡이 에이스 뺀 전체를 넘기면
    # 에이스는 자동으로 범위 밖 → 다른 잡이 관리하는 창고 행을 잘못 삭제하지 않음)
    if warehouse_scope is None:
        warehouse_scope = sorted(azy_df["창고"].dropna().astype(str).unique().tolist())

    with get_conn() as conn:
        with conn.cursor() as cur:
            if warehouse_scope:
                placeholders = ", ".join(["%s"] * len(warehouse_scope))
                cur.execute(
                    "SELECT id, 홀딩, 상태, 메모, 상품명, 브랜드, 등급, ESTNO, 평중, 유통기한, 출고일 "
                    f"FROM azy_inventory WHERE 수집일 != '' AND 창고 IN ({placeholders})",
                    tuple(warehouse_scope),
                )
            else:
                cur.execute(
                    "SELECT id, 홀딩, 상태, 메모, 상품명, 브랜드, 등급, ESTNO, 평중, 유통기한, 출고일 "
                    "FROM azy_inventory WHERE 수집일 != ''"
                )
            existing = {row["id"]: row for row in cur.fetchall()}

        # 사용자가 UI에서 직접 고칠 수 있는 마스터 필드 — 기존 행이면 크롤값으로 덮어쓰지 않고 보존
        for uid, data in rows.items():
            prev = existing.get(uid)
            data["홀딩"] = prev.get("홀딩", "") if prev else ""
            data["상태"] = prev.get("상태", "없음") if prev else "없음"
            data["메모"] = prev.get("메모", "") if prev else ""
            if prev:
                for f in ("상품명", "브랜드", "등급", "ESTNO", "평중", "유통기한", "출고일"):
                    if prev.get(f) not in (None, ""):
                        data[f] = prev[f]

        stale_ids = [uid for uid in existing if uid not in rows]

        upsert_azy_inventory(conn, list(rows.values()))
        if stale_ids:
            delete_azy_inventory(conn, stale_ids)

    log.info(f"  [azy] {len(rows)}건 갱신 / {len(stale_ids)}건 삭제 → azy_inventory 완료")


def run_pipeline():
    """JNS·에이스를 제외한 나머지 창고 전용 — azy_inventory만 갱신.
    JNS가 크롤링 시간을 지배해 전체 사이클을 늦추던 문제를 없애기 위해
    JNS는 run_jns_pipeline()으로, 에이스는 run_ace_pipeline()으로 완전히 분리했다."""
    start = time.time()
    log.info("─" * 50)
    log.info("파이프라인 시작")

    try:
        # 1. 병렬 크롤링 (JNS 제외 — 별도 잡에서 독립 실행)
        results = crawler.crawl_all(exclude=[JNS_WAREHOUSE])

        failed = [w for w, df in results.items() if df is None or (hasattr(df, "empty") and df.empty)]
        if failed:
            log.warning(f"실패 창고: {', '.join(failed)}")

        # 2. 정규화 (타창고 → azy_inventory. JNS는 어차피 crawl_all에서 빠졌으니 빈 값)
        _normalized, azy_normalized = crawler.normalize(results)
        if azy_normalized.empty:
            log.warning("정규화 후 데이터 없음 - 이번 라운드 스킵")
            return

        # 3. azy_inventory 업데이트
        _upload_azy(azy_normalized)

        elapsed = time.time() - start
        log.info(f"완료 | azy {len(azy_normalized)}건 | {elapsed:.1f}초 소요")

    except Exception as e:
        log.error(f"파이프라인 오류: {e}", exc_info=True)


def run_jns_pipeline():
    """JNS(제니스) 전용 — 나머지 창고와 완전히 독립적으로 실행.
    JNS는 데이터량이 압도적으로 커서 같은 크롤 배치에 있으면 전체 사이클의
    하한선을 정해버리므로, 자기 페이스대로 도는 별도 잡으로 분리."""
    start = time.time()
    jns_log.info("─" * 50)
    jns_log.info("JNS 파이프라인 시작")

    try:
        # 1. 단독 크롤링
        jns_raw = crawler.crawl_one(JNS_WAREHOUSE)
        if jns_raw is None or jns_raw.empty:
            jns_log.warning("JNS 크롤링 실패/데이터 없음 - 이번 라운드 스킵")
            return

        # 2. 정규화 (list_eda()의 JNS 처리 블록만 재사용)
        from back_end.back_eda_main import jns_only_eda
        normalized = jns_only_eda(jns_raw)
        if normalized.empty:
            jns_log.warning("정규화 후 데이터 없음 - 이번 라운드 스킵")
            return

        # 3. inventory diff 업데이트
        prev = snapshot.load()
        changed, new_snap = updater.update_diff(normalized, prev)
        snapshot.save(new_snap)

        import pandas as _pd
        eda_qty = int(_pd.to_numeric(normalized["재고수량"], errors="coerce").fillna(0).sum()) \
            if "재고수량" in normalized.columns else 0
        fs_qty  = sum(v.get("재고", 0) or 0 for v in new_snap.values())
        qty_diff = eda_qty - fs_qty
        qty_note = f" ★ {qty_diff}박스 차이" if qty_diff != 0 else ""

        elapsed = time.time() - start
        jns_log.info(
            f"완료 | EDA {len(normalized)}건/{eda_qty}박스 → MySQL {len(new_snap)}건/{fs_qty}박스{qty_note} | 변경 {changed}건 | {elapsed:.1f}초 소요"
        )

    except Exception as e:
        jns_log.error(f"JNS 파이프라인 오류: {e}", exc_info=True)


def run_ace_pipeline():
    """에이스냉장(기흥/처인/용인) 전용 — 동시접속 1명 제한(2번째부터 404)이라
    메인 1분 주기와 완전히 분리해 정각마다 단독 실행한다."""
    start = time.time()
    ace_log.info("─" * 50)
    ace_log.info("에이스 파이프라인 시작")

    try:
        from back_end.crawling_handmade import crawling_ace
        from back_end.replace_name import replace_name
        from back_end.eda_standard import eda_standard

        ace_df = crawling_ace()
        if ace_df is None or ace_df.empty:
            ace_log.warning("에이스 데이터 없음 - 이번 라운드 스킵")
            return

        ace_df = replace_name(ace_df)
        ace_df = eda_standard(ace_df)
        ace_df = replace_name(ace_df)
        ace_df = ace_df.drop_duplicates().reset_index(drop=True)

        _upload_azy(ace_df)

        elapsed = time.time() - start
        ace_log.info(f"완료 | {len(ace_df)}건 | {elapsed:.1f}초 소요")

    except Exception as e:
        ace_log.error(f"에이스 파이프라인 오류: {e}", exc_info=True)


def _in_operating_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # 토(5), 일(6) 제외
        return False
    return (dt.hour == 8 and dt.minute == 0) or \
           (8 < dt.hour < 17) or \
           (dt.hour == 17 and dt.minute == 0)


def main():
    log.info("=" * 50)
    log.info("창고 재고 파이프라인 서비스 시작")
    log.info("스케줄: 나머지창고/JNS 평일 08:00~17:00 1분 간격(서로 독립) + 에이스 정각 1시간 간격 별도")
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

    # JNS(제니스) 전용 — 나머지 창고와 같은 1분 간격이지만 완전히 독립된 잡.
    # JNS가 오래 걸려도 나머지 창고 사이클을 기다리게 하지 않는다.
    scheduler.add_job(
        run_jns_pipeline,
        trigger,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        id="jns_pipeline",
    )

    # 에이스냉장 전용 — 평일 08~17시 정각(1시간 간격)에만, 메인 잡과 완전히 독립적으로 실행.
    # 동시접속 1명 제한 사이트라 메인 파이프라인 소요시간(최대 ~150초)과 무관하게
    # 매 정각에 정확히 트리거되도록 별도 잡으로 분리.
    scheduler.add_job(
        run_ace_pipeline,
        CronTrigger(hour="8-17", minute="0", day_of_week="mon-fri", timezone="Asia/Seoul"),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        id="ace_pipeline",
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
        run_jns_pipeline()
    else:
        log.info(f"현재 시각 {now.strftime('%H:%M')} - 운영 시간(평일 08:00~17:00) 외, 다음 평일 08:00까지 대기")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("서비스 종료")


if __name__ == "__main__":
    main()
