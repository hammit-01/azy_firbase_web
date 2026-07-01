"""
Firestore 이중화 업데이터  (Primary + Secondary 폴백)

할당량 초과 시 Secondary로 자동 전환, 23시간 후 Primary 복귀 시도.

★ Secondary 설정:
  1. https://console.firebase.google.com 에서 새 프로젝트 생성
  2. 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성 → JSON 다운로드
  3. 파일을 프로젝트 루트에 두고 CRED_PATH_SECONDARY 값을 교체
  4. front_end/html/js/firebase.js 의 SECONDARY_CONFIG 도 교체
"""
import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

try:
    from google.api_core.exceptions import ResourceExhausted as _QuotaError
except ImportError:
    _QuotaError = None

log = logging.getLogger("updater")

CRED_PATH_PRIMARY   = "azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json"
CRED_PATH_SECONDARY = "awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json"
COLLECTION     = "all_data"
BATCH_LIMIT    = 250
ACTIVE_DB_FILE = Path("pipeline/active_db.json")
RECOVERY_HOURS = 23  # Secondary 전환 후 N시간 뒤 Primary 복귀 시도

COMPARE_FIELDS = (
    "상품명", "브랜드", "등급", "ESTNO", "재고",
    "BL", "창고", "유통기한", "평중", "출고일",
    # 홀딩·상태·메모는 사용자 설정 필드 → 파이프라인 비교/덮어쓰기 대상 제외
)


def _row_sig(data: dict) -> str:
    return "|".join(str(data.get(k) or "") for k in COMPARE_FIELDS)


def _is_quota_error(e: Exception) -> bool:
    if _QuotaError and isinstance(e, _QuotaError):
        return True
    msg = str(e)
    return any(kw in msg for kw in ("Quota exceeded", "RESOURCE_EXHAUSTED", "429"))


# ── DB 싱글턴 ──────────────────────────────────────────────
_db_primary   = None
_db_secondary = None
_lock  = threading.Lock()
_active = "primary"  # "primary" | "secondary"


def _load_active_state():
    global _active
    if ACTIVE_DB_FILE.exists():
        try:
            _active = json.loads(
                ACTIVE_DB_FILE.read_text(encoding="utf-8")
            ).get("active", "primary")
        except Exception:
            _active = "primary"


def _save_active_state(switched_at=None):
    data = {"active": _active}
    if switched_at:
        data["switched_at"] = switched_at
    ACTIVE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_DB_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _get_primary_db():
    global _db_primary
    if _db_primary is None:
        with _lock:
            if _db_primary is None:
                cred = credentials.Certificate(CRED_PATH_PRIMARY)
                try:
                    app = firebase_admin.get_app("[DEFAULT]")
                except ValueError:
                    app = firebase_admin.initialize_app(cred)
                _db_primary = firestore.client(app)
    return _db_primary


def _get_secondary_db():
    global _db_secondary
    if not Path(CRED_PATH_SECONDARY).exists():
        return None
    if _db_secondary is None:
        with _lock:
            if _db_secondary is None:
                cred = credentials.Certificate(CRED_PATH_SECONDARY)
                try:
                    app = firebase_admin.get_app("secondary")
                except ValueError:
                    app = firebase_admin.initialize_app(cred, name="secondary")
                _db_secondary = firestore.client(app)
    return _db_secondary


def _activate_secondary():
    global _active
    _active = "secondary"
    now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    _save_active_state(switched_at=now_iso)
    sec = _get_secondary_db()
    if sec:
        try:
            sec.collection("_meta").document("active_db").set(
                {"active": "secondary", "switched_at": now_iso}
            )
        except Exception as e:
            log.warning(f"Secondary 마커 기록 실패: {e}")
    log.warning("★ [SECONDARY] DB 전환 완료 - 프론트엔드가 자동 감지해 전환됩니다")


def _activate_primary():
    global _active
    _active = "primary"
    _save_active_state()
    sec = _get_secondary_db()
    if sec:
        try:
            sec.collection("_meta").document("active_db").delete()
        except Exception as e:
            log.warning(f"Secondary 마커 삭제 실패: {e}")
    log.info("★ [PRIMARY] DB 복귀 완료")


def _should_try_recovery() -> bool:
    if _active != "secondary":
        return False
    try:
        data = json.loads(ACTIVE_DB_FILE.read_text(encoding="utf-8"))
        ts = data.get("switched_at")
        if not ts:
            return True
        elapsed = (
            datetime.now(ZoneInfo("Asia/Seoul")) - datetime.fromisoformat(ts)
        ).total_seconds()
        return elapsed > RECOVERY_HOURS * 3600
    except Exception:
        return True


def _clean(s: str) -> str:
    return re.sub(r"[/\s]", "_", s.strip())


def _df_to_dict(df: pd.DataFrame, today: str, holding_sum: dict = None) -> tuple:
    """Returns (result_dict, crawled_key_totals) where crawled_key_totals maps
    (bl, name, expire) → total raw qty BEFORE holding deduction."""
    from post import to_str, to_int, to_float, to_date
    if holding_sum is None:
        holding_sum = {}
    result = {}
    crawled_key_totals = {}   # 홀딩 이상 감지용: 차감 전 원본 수량
    skipped_rows, skipped_qty = 0, 0
    merged_rows,  merged_qty  = 0, 0
    raw_total = 0

    for _, row in df.iterrows():
        code   = to_str(row.get("코드", "")).strip()
        bl     = to_str(row.get("BL번호", "")).strip()
        est    = to_str(row.get("식별번호", "")).strip()
        name   = to_str(row.get("수탁품", "")).strip()
        expire = to_date(row.get("유통기한"))
        qty    = to_int(row.get("재고수량"))
        raw_total += qty

        # doc_id: 코드_BL뒤4자리_식별번호뒤4자리_유통기한
        expire_str = expire.replace("-", "") if expire else ""
        bl_last4   = _clean(bl[-4:] if len(bl) >= 4 else bl)
        est_last4  = _clean(est[-4:] if len(est) >= 4 else est) if est else ""
        doc_id     = f"{_clean(code)}_{bl_last4}_{est_last4}_{expire_str}"

        if not doc_id or doc_id.replace("_", "") == "":
            skipped_rows += 1
            skipped_qty  += qty
            log.warning(f"  pk 생성 불가 스킵: 수탁품={name[:20]} / 재고={qty}박스")
            continue

        # 홀딩 이상 감지: 차감 전 원본 수량 누적
        key = (bl, name, expire)
        crawled_key_totals[key] = crawled_key_totals.get(key, 0) + qty

        # 홀딩 차감
        h_qty   = holding_sum.get(key, 0)
        net_qty = qty - h_qty
        if net_qty <= 0:
            skipped_rows += 1
            skipped_qty  += qty
            log.info(f"  홀딩 전량 차감 스킵: {name[:20]} / 크롤={qty} 홀딩={h_qty}")
            continue

        data = {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": name,
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO":  to_str(row.get("ESTNO", "")).strip(),
            "재고":   net_qty,
            "BL":     bl,
            "창고":   to_str(row.get("창고", "")).strip(),
            "유통기한": expire,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고일")),
            "수집일": today,
        }
        if doc_id in result:
            # 동일 pk: 창고 코드 달라도 같은 상품 → 재고 합산
            merged_rows += 1
            merged_qty  += net_qty
            result[doc_id]["재고"] = (result[doc_id].get("재고") or 0) + net_qty
        else:
            result[doc_id] = data

    out_total = sum(v.get("재고", 0) or 0 for v in result.values())
    log.info(
        f"  [변환] 원본 {len(df)}행 {raw_total}박스 → Firestore {len(result)}건 {out_total}박스"
    )
    if skipped_rows:
        log.warning(f"  [변환] pk없음/홀딩차감 스킵: {skipped_rows}행 {skipped_qty}박스")
    if merged_rows:
        log.info(f"  [변환] pk병합: {merged_rows}행 → 재고 합산 {merged_qty}박스")

    return result, crawled_key_totals


def _batch_set(db, items: dict):
    """신규 문서 생성 — set() 으로 전체 덮어쓰기 (사용자 기본값 포함)"""
    keys = list(items.keys())
    for i in range(0, len(keys), BATCH_LIMIT):
        batch = db.batch()
        for pk in keys[i:i + BATCH_LIMIT]:
            batch.set(db.collection(COLLECTION).document(pk), items[pk])
        batch.commit()


def _batch_merge(db, items: dict):
    """기존 문서 업데이트 — set(merge=True) 로 크롤링 필드만 갱신, 사용자 필드 보존"""
    keys = list(items.keys())
    for i in range(0, len(keys), BATCH_LIMIT):
        batch = db.batch()
        for pk in keys[i:i + BATCH_LIMIT]:
            batch.set(db.collection(COLLECTION).document(pk), items[pk], merge=True)
        batch.commit()


def _batch_delete(db, pks: list):
    for i in range(0, len(pks), BATCH_LIMIT):
        batch = db.batch()
        for pk in pks[i:i + BATCH_LIMIT]:
            batch.delete(db.collection(COLLECTION).document(pk))
        batch.commit()


def _batch_flag(db, updates: list):
    """holding doc의 이상/원본재고 필드 부분 업데이트"""
    for i in range(0, len(updates), BATCH_LIMIT):
        batch = db.batch()
        for (doc_id, fields) in updates[i:i + BATCH_LIMIT]:
            batch.update(db.collection(COLLECTION).document(doc_id), fields)
        batch.commit()


class FirestoreUpdater:
    def __init__(self):
        _load_active_state()
        log.info(f"FirestoreUpdater 시작 - 활성 DB: {_active.upper()}")

    def update_diff(self, new_df: pd.DataFrame, prev_snapshot: dict) -> tuple:
        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

        # 활성 DB 결정
        db = _get_primary_db() if _active == "primary" else (
            _get_secondary_db() or _get_primary_db()
        )

        # 홀딩 행 선조회: (BL, 상품명, 유통기한) → 홀딩 수량 합계
        # holding 행은 수집일이 빈 문자열 (크롤링 원본 행만 수집일 존재)
        holding_sum: dict = {}
        holding_doc_map: dict = {}   # key → [(doc_id, cur_이상), ...] — 이상 감지용
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            # 백틱 인용으로 한국어 필드명 Firestore 쿼리 가능
            for hdoc in db.collection(COLLECTION).where(filter=FieldFilter("`수집일`", "==", "")).stream():
                h = hdoc.to_dict()
                if str(h.get("상태", "")).strip() != "holding":
                    continue
                key = (
                    str(h.get("BL",    "")).strip(),
                    str(h.get("상품명", "")).strip(),
                    str(h.get("유통기한", "")).strip(),
                )
                holding_sum[key] = holding_sum.get(key, 0) + int(h.get("재고", 0) or 0)
                holding_doc_map.setdefault(key, []).append(
                    (hdoc.id, str(h.get("이상", "") or ""))
                )
            if holding_sum:
                log.info(f"  홀딩 데이터 {len(holding_sum)}건 조회 완료")
        except Exception as e:
            log.warning(f"  홀딩 데이터 조회 실패 (무시하고 진행): {e}")

        new_data, crawled_key_totals = _df_to_dict(new_df, today, holding_sum)

        to_insert = {}   # 신규 문서: 사용자 필드 기본값 포함해 set()
        to_update = {}   # 변경된 기존 문서: 크롤링 필드만 merge()
        to_delete = []

        for pk, data in new_data.items():
            prev = prev_snapshot.get(pk)
            if prev is None:
                # 신규: 사용자 필드 초기값 함께 생성
                to_insert[pk] = {**data, "홀딩": "", "상태": "없음", "메모": ""}
            elif _row_sig(prev) != _row_sig(data):
                # 변경: 크롤링 필드만 업데이트 (홀딩·상태·메모 보존)
                to_update[pk] = data

        for pk in prev_snapshot:
            if pk not in new_data:
                to_delete.append(pk)

        total = len(to_insert) + len(to_update) + len(to_delete)

        if total == 0:
            log.info("  변경 없음")
            if _should_try_recovery():
                self._try_recover_primary(new_data, [])
            return 0, new_data

        # ── Secondary 사용 중이고 23시간 경과 시 Primary 복귀 시도 ──
        if _should_try_recovery():
            if self._try_recover_primary(new_data, to_delete):
                return total, new_data

        # ── 활성 DB에 쓰기 ─────────────────────────────────────
        try:
            if to_insert:
                _batch_set(db, to_insert)
            if to_update:
                _batch_merge(db, to_update)
            if to_delete:
                _batch_delete(db, to_delete)
            log.info(f"  [{_active.upper()}] ↑{len(to_insert)}건(신규) ↻{len(to_update)}건(갱신) ✕{len(to_delete)}건")

            # ── 홀딩 이상 감지 및 플래그 ──────────────────────────
            self._flag_holding_issues(db, holding_doc_map, holding_sum, crawled_key_totals)

            return total, new_data

        except Exception as e:
            if not _is_quota_error(e):
                raise
            log.warning(f"  [{_active.upper()}] 할당량 초과")
            return self._fallback_to_secondary(new_data, prev_snapshot)

    def _flag_holding_issues(self, db, holding_doc_map: dict, holding_sum: dict, crawled_key_totals: dict):
        """홀딩 doc에 이상/원본재고 필드를 기록하거나 해소 시 클리어한다."""
        if not holding_doc_map:
            return
        flag_updates = []
        for key, doc_list in holding_doc_map.items():
            h_total    = holding_sum.get(key, 0)
            crawled_qty = crawled_key_totals.get(key, 0)

            if crawled_qty == 0:
                issue, orig_qty = "원본없음", 0
            elif crawled_qty < h_total:
                issue, orig_qty = "수량초과", crawled_qty
            else:
                issue, orig_qty = "", ""

            for (doc_id, cur_issue) in doc_list:
                if cur_issue != issue:
                    flag_updates.append((doc_id, {"이상": issue, "원본재고": orig_qty}))

        if flag_updates:
            try:
                _batch_flag(db, flag_updates)
                issues = [f for _, f in flag_updates if f.get("이상")]
                clears = len(flag_updates) - len(issues)
                if issues:
                    log.warning(f"  [홀딩이상] 신규/변경 {len(issues)}건 플래그")
                if clears:
                    log.info(f"  [홀딩이상] 해소 클리어 {clears}건")
            except Exception as e:
                log.warning(f"  홀딩 이상 플래그 실패 (무시): {e}")

    def _fallback_to_secondary(self, new_data: dict, prev_snapshot: dict) -> tuple:
        if _active != "primary":
            log.error("  Secondary도 할당량 초과 - 이번 라운드 스킵")
            return 0, prev_snapshot

        log.warning("  Primary 초과 → Secondary 전환 시작")
        _activate_secondary()

        sec = _get_secondary_db()
        if sec is None:
            log.error(f"  Secondary credential 없음({CRED_PATH_SECONDARY})")
            log.error("  ★ 위 경로에 새 Firebase 프로젝트의 Admin SDK JSON을 두세요")
            return 0, prev_snapshot

        try:
            # 신규 doc에 사용자 필드 기본값 포함해 생성 (merge=True이므로 기존 홀딩·메모는 보존)
            enriched = {pk: {**d, "상태": "없음", "홀딩": "", "메모": ""} for pk, d in new_data.items()}
            _batch_merge(sec, enriched)
            log.info(f"  [SECONDARY] 초기 전체 기록 {len(new_data)}건 완료")
            return len(new_data), new_data
        except Exception as e:
            if _is_quota_error(e):
                log.error("  Secondary도 할당량 초과 - 스킵")
            else:
                log.error(f"  Secondary 쓰기 오류: {e}")
            return 0, prev_snapshot

    def _try_recover_primary(self, new_data: dict, to_delete: list) -> bool:
        log.info(f"  {RECOVERY_HOURS}시간 경과 - Primary 복귀 시도")
        pri = _get_primary_db()
        try:
            if new_data:
                _batch_merge(pri, new_data)
            if to_delete:
                _batch_delete(pri, to_delete)
            _activate_primary()
            log.info(f"  [PRIMARY] 복귀 성공 - {len(new_data)}건 동기화 / {len(to_delete)}건 삭제")
            # Primary 복귀 성공 시 employees를 Secondary에 동기화
            # (다음 Secondary 전환 대비)
            try:
                sec = _get_secondary_db()
                if sec:
                    emp_docs = list(pri.collection("employees").stream())
                    if emp_docs:
                        batch = sec.batch()
                        for d in emp_docs:
                            batch.set(sec.collection("employees").document(d.id), d.to_dict())
                        batch.commit()
                        log.info(f"  employees {len(emp_docs)}명 Secondary 동기화 완료")
            except Exception as e:
                log.warning(f"  employees Secondary 동기화 실패 (무시): {e}")
            return True
        except Exception as e:
            if _is_quota_error(e):
                log.info("  Primary 아직 할당량 초과 - Secondary 유지")
            else:
                log.error(f"  Primary 복귀 오류: {e}")
            return False
