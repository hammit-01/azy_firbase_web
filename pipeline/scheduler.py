import faulthandler
import logging
import logging.handlers
import signal
import sys
import time
from contextlib import contextmanager
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

# 사이클이 멈추면 원인 추적할 방법이 없던 문제(2026-07-28) — py-spy는 Windows에서
# 관리자 권한으로도 세션 문제로 안 붙음(os error 87). 대신 프로세스가 스스로
# 전체 스레드 스택을 덤프하는 stdlib faulthandler를 사이클마다 타이머로 걸어둔다.
# 참고: dump_traceback_later는 프로세스 전역에 하나만 걸리므로, 메인/JNS 잡이
# 동시에 걸리면 나중에 건 쪽 타이머만 유효함 — 진단용이라 감수.
HANG_DUMP_PATH = LOG_DIR / "hang_dump.log"

@contextmanager
def _hang_watchdog(label: str, timeout: int = 90):
    f = open(HANG_DUMP_PATH, "a", encoding="utf-8")
    f.write(f"\n===== {datetime.now()} [{label}] {timeout}초 넘게 안 끝나면 아래 덤프 =====\n")
    f.flush()
    faulthandler.dump_traceback_later(timeout, repeat=False, file=f, exit=False)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
        f.close()

# 로테이션 없이 계속 쌓이던 문제 — 10MB x 5개(파일당)로 제한
def _rotating_handler(path):
    return logging.handlers.RotatingFileHandler(
        path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        _rotating_handler(LOG_DIR / "pipeline.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("scheduler")

# ── 에이스냉장 전용 로거 (동시접속 1명 제한 — 별도 정각 스케줄) ──
# propagate=False로 메인 pipeline.log에는 섞이지 않고 pipeline_ace.log에만 기록
ace_log = logging.getLogger("ace_scheduler")
ace_log.setLevel(logging.INFO)
ace_log.propagate = False
_ace_handler = _rotating_handler(LOG_DIR / "pipeline_ace.log")
_ace_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
ace_log.addHandler(_ace_handler)

# ── JNS(제니스) 전용 로거 — 나머지 창고 사이클과 완전히 독립 실행 ──
jns_log = logging.getLogger("jns_scheduler")
jns_log.setLevel(logging.INFO)
jns_log.propagate = False
_jns_handler = _rotating_handler(LOG_DIR / "pipeline_jns.log")
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
        with conn.cursor() as cur:
            # 대청은 통관분(JNS/곤대청) 계정과 일반(azy/대청) 계정이 같은 재고를 그대로
            # 보여줘서 BL이 겹치면 두 테이블에 통째로 중복 적재된다(2026-08-03, DB에
            # 실제 중복 7건 발견 후 삭제) — 곤대청에 이미 있는 BL은 azy 쪽에 아예 안 쌓음.
            cur.execute("SELECT BL FROM inventory WHERE 창고='곤대청' AND BL != ''")
            gon_daecheong_bls = {row["BL"] for row in cur.fetchall()}

    rows = {}
    for _, r in azy_df.iterrows():
        bl    = _s(r.get("BL번호"))
        estno = _s(r.get("ESTNO") or r.get("식별번호", ""))
        grade = _s(r.get("등급"))
        wh    = _s(r.get("창고"))
        name  = _s(r.get("수탁품"))
        if wh == "대청" and bl in gon_daecheong_bls:
            continue
        # 등급·상품명도 식별자에 포함 — 같은 BL+ESTNO라도 등급(CH/UN 등)이 다르면 별도 재고이고,
        # 같은 BL+ESTNO+등급이라도 상품명이 다르면(한 BL에 서로 다른 상품이 같이 실려온 경우) 별도 상품이므로
        # 로트/저장위치 중복 합산 대상이 아님
        uid   = f"{bl}_{estno}_{grade}_{name}_{wh}" if bl else uuid.uuid4().hex
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
            "_auto_상태": _s(r.get("_auto_상태")),
            "_auto_메모": _s(r.get("_auto_메모")),
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
                    "SELECT id, 홀딩, 상태, 메모, 상품명, 브랜드, 등급, ESTNO, BL, 창고, 재고, 평중, 유통기한, 출고일 "
                    f"FROM azy_inventory WHERE 수집일 != '' AND 창고 IN ({placeholders})",
                    tuple(warehouse_scope),
                )
            else:
                cur.execute(
                    "SELECT id, 홀딩, 상태, 메모, 상품명, 브랜드, 등급, ESTNO, BL, 창고, 재고, 평중, 유통기한, 출고일 "
                    "FROM azy_inventory WHERE 수집일 != ''"
                )
            existing = {row["id"]: row for row in cur.fetchall()}

        # 사용자가 UI에서 직접 고칠 수 있는 마스터 필드 — 기존 행이면 크롤값으로 덮어쓰지 않고 보존
        for uid, data in rows.items():
            prev = existing.get(uid)
            auto_state = data.pop("_auto_상태", "")
            auto_memo  = data.pop("_auto_메모", "")
            data["홀딩"] = prev.get("홀딩", "") if prev else ""

            if prev:
                # 재고는 절대 여기 넣지 않음 — 매 사이클 크롤 원본 기준으로 다시 계산돼야 함
                # (2026-07-31: BL/창고를 여기 추가했는데 existing SELECT에 그 컬럼들이
                # 빠져있어서 prev.get()이 항상 None이라 실제로는 한 번도 안 먹히던 사고 —
                # SELECT 쪽(위 existing 조회)에 BL/창고/재고 컬럼 추가로 같이 수정함)
                for f in ("상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "평중", "유통기한", "출고일"):
                    if prev.get(f) not in (None, ""):
                        data[f] = prev[f]

            prev_state = prev.get("상태", "없음") if prev else "없음"
            if prev_state == "holding":
                # 실제 홀딩 처리 중인 행은 자동 로직이 건드리지 않음
                data["상태"] = prev_state
                data["메모"] = prev.get("메모", "") if prev else ""
            else:
                # holding이 아니면 매 사이클 최신 데이터(위 보존 반영 후 최종값) 기준으로 재계산
                # — 결측이 나중에 채워지거나 새로 결측이 생겨도 상태가 계속 따라감
                is_missing = any(
                    not str(data.get(f, "")).strip()
                    for f in ("상품명", "브랜드", "등급", "ESTNO")
                )
                prev_memo = prev.get("메모", "") if prev else ""
                if auto_state == "특이품":
                    data["상태"] = "특이품"
                    data["메모"] = auto_memo
                elif "검품" in str(prev_memo):
                    # 메모에 "검품"이 남아있으면(사람이 직접 남긴 태그) 상태를 특이품으로 강제
                    data["상태"] = "특이품"
                    data["메모"] = prev_memo
                elif is_missing:
                    data["상태"] = "null"
                    data["메모"] = prev_memo
                else:
                    data["상태"] = "없음"
                    data["메모"] = prev_memo

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
        with _hang_watchdog("run_pipeline"):
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
            # stale 삭제 범위를 azy_normalized["창고"]로 자동 추론하면, 어떤 창고의
            # 재고가 전부 빠져 이번 크롤 결과에 그 창고 행이 하나도 없을 때 그 창고가
            # 범위에서 통째로 빠져서 마지막 재고가 영원히 안 지워지고 남는다(2026-08-03,
            # 에이스용인 사고와 같은 패턴). 크롤 자체가 성공한(df가 None이 아닌) 창고는
            # 결과가 0건이어도 범위에 포함 — 크롤이 실패(None)한 창고만 제외해서
            # 일시적 장애로 기존 정상 데이터가 잘못 지워지는 건 막는다.
            crawled_scope = [w for w, df in results.items() if df is not None]
            _upload_azy(azy_normalized, warehouse_scope=crawled_scope)

            # 3-1. 이고(창고이동) 취합 시트 → moving_inventory 동기화 + 재고 반영.
            # azy_inventory에 이번 사이클 최신 재고가 막 반영된 직후에 돌려야
            # 이고 차감이 이번 크롤로 곧바로 덮어써지지 않는다(다음 사이클까지 안 밀림).
            # 1) 이동창고에 이미 이고 수량만큼 입고돼 있으면 그 행은 제외(입고 완료).
            # 2) 남은(미입고) 행만 출고창고 쪽 재고에서 차감 — 홀딩처럼 매 사이클 재계산.
            try:
                from pipeline.moving_reader import load_moving_rows
                from pipeline.mysql_db import get_conn as _get_conn, sync_moving_inventory, apply_moving_deductions
                moving_rows = load_moving_rows()
                with _get_conn() as conn:
                    # inventory(JNS)는 run_jns_pipeline이 독립 스케줄로 원본을 덮어쓰므로
                    # 여기서는 방금 갱신한 azy_inventory만 차감한다 (이중/유실 차감 방지).
                    remaining_rows = apply_moving_deductions(conn, moving_rows, deduct_targets=("azy_inventory",))
                    sync_moving_inventory(conn, remaining_rows)
            except Exception as e:
                log.warning(f"이고 동기화 실패: {e}")

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
        with _hang_watchdog("run_jns_pipeline"):
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

            # 3-1. 이고 차감 재적용 — 방금 크롤 원본으로 inventory 재고가 덮였으므로
            # moving_inventory에 남아있는(미입고) 행 기준으로 inventory 쪽만 다시 뺀다.
            # moving_inventory 자체는 run_pipeline이 시트에서 다시 읽어 갱신하므로
            # 여기선 현재 저장된 내용만 읽어 재적용한다.
            try:
                from pipeline.mysql_db import get_conn as _get_conn, apply_moving_deductions
                with _get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 상품명, 브랜드, 등급, ESTNO, BL, 재고, 출고창고, 이동창고 FROM moving_inventory"
                        )
                        current_moving = cur.fetchall()
                    apply_moving_deductions(conn, current_moving, deduct_targets=("inventory",))
            except Exception as e:
                jns_log.warning(f"이고 차감 재적용 실패: {e}")

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
        with _hang_watchdog("run_ace_pipeline"):
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
            # drop_duplicates()는 쓰지 않음: 서로 다른 로트가 상품/BL/재고수량/유통기한까지
            # 우연히 완전히 같으면 한쪽이 통째로 삭제되어 박스 수가 조용히 손실된다
            # (이 코드베이스 전역에서 금지하는 패턴 — back_eda_main.py의 azy_data와
            # 동일하게 재고수량만 별도로 합산). 2026-08-03, 다른 창고들엔 이미 적용된
            # 이 보호가 에이스 경로에만 빠져있던 걸 발견해 같이 맞춤.
            if "재고수량" in ace_df.columns:
                import pandas as _pd
                ace_df["재고수량"] = _pd.to_numeric(
                    ace_df["재고수량"].astype(str).str.replace(",", "", regex=False),
                    errors="coerce"
                ).fillna(0).astype(int)
                group_cols = [c for c in ace_df.columns if c != "재고수량"]
                ace_df = ace_df.groupby(group_cols, dropna=False, sort=False)["재고수량"].sum().reset_index()
            else:
                ace_df = ace_df.drop_duplicates().reset_index(drop=True)

            # 창고 하나(예: 용인)의 재고가 전부 빠져서 이번 크롤 결과에 그 창고 행이
            # 하나도 없으면, _upload_azy의 자동 scope(azy_df["창고"] 기준)가 그 창고를
            # stale 삭제 범위에서 빠뜨려 마지막 재고가 영원히 안 지워지고 남는다
            # (2026-08-03, 에이스용인 5일 전 재고가 안 지워지고 남아있던 사고 발견) —
            # 에이스 3개 창고는 항상 고정 scope로 명시.
            _upload_azy(ace_df, warehouse_scope=["에이스기흥", "에이스처인", "에이스용인"])

        elapsed = time.time() - start
        ace_log.info(f"완료 | {len(ace_df)}건 | {elapsed:.1f}초 소요")

    except Exception as e:
        ace_log.error(f"에이스 파이프라인 오류: {e}", exc_info=True)


def run_daily_snapshot():
    """평일 장 마감(17:10) 직후 1회 — 오늘 최종 재고를 yesterday_* 테이블로 복사.
    업데이트 탭이 다음날 이 스냅샷과 비교해서 "어제 대비 뭐가 바뀌었나"를 보여준다."""
    log.info("일일 스냅샷(yesterday_inventory) 갱신 시작")
    try:
        from pipeline.mysql_db import get_conn, snapshot_daily
        with get_conn() as conn:
            snapshot_daily(conn)
        log.info("일일 스냅샷 갱신 완료")
    except Exception as e:
        log.error(f"일일 스냅샷 갱신 실패: {e}", exc_info=True)


def reset_changes_log():
    """changes_log 월간 초기화 — 매달 1일 자정에 통째로 비움."""
    log.info("changes_log 월간 초기화")
    try:
        from pipeline.mysql_db import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE changes_log")
        log.info("changes_log 초기화 완료")
    except Exception as e:
        log.error(f"changes_log 초기화 실패: {e}")


def _in_operating_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # 토(5), 일(6) 제외
        return False
    return (dt.hour == 8 and dt.minute == 0) or \
           (8 < dt.hour < 17) or \
           (dt.hour == 17 and dt.minute == 0)


def main():
    from back_end.crawling_handmade import cleanup_orphaned_chrome
    log.info("이전 실행에서 남은 좀비 헤드리스 크롬 정리 중...")
    cleanup_orphaned_chrome()

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

    # 에이스냉장 전용 — 평일 08~16시 정각 + 16:59(마지막 실행)에, 메인 잡과 완전히 독립적으로 실행.
    # 동시접속 1명 제한 사이트라 메인 파이프라인 소요시간(최대 ~150초)과 무관하게
    # 매 정각에 정확히 트리거되도록 별도 잡으로 분리. 마지막 실행만 17:00 대신 16:59로 앞당김.
    ace_trigger = OrTrigger([
        CronTrigger(hour="8-16", minute="0", day_of_week="mon-fri", timezone="Asia/Seoul"),
        CronTrigger(hour="16",   minute="59", day_of_week="mon-fri", timezone="Asia/Seoul"),
    ])

    scheduler.add_job(
        run_ace_pipeline,
        ace_trigger,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        id="ace_pipeline",
    )

    # 매달 1일 00:00에 changes_log 통째로 초기화
    scheduler.add_job(
        reset_changes_log,
        CronTrigger(day=1, hour=0, minute=0, timezone="Asia/Seoul"),
        id="changes_log_reset",
    )

    # 평일 장 마감(17:10, 메인/JNS 17:00·에이스 16:59 마지막 실행 이후) 스냅샷
    scheduler.add_job(
        run_daily_snapshot,
        CronTrigger(hour="17", minute="10", day_of_week="mon-fri", timezone="Asia/Seoul"),
        id="daily_snapshot",
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
