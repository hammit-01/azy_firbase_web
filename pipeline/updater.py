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
    "BL", "창고", "유통기한", "평중", "출고일", "홀딩", "상태",
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


def _df_to_dict(df: pd.DataFrame, today: str) -> dict:
    from post import to_str, to_int, to_float, to_date
    result = {}
    for _, row in df.iterrows():
        bl     = to_str(row.get("BL번호", "")).strip()
        code   = to_str(row.get("코드", "")).strip().replace("/", "_").replace(" ", "_")
        expire = to_date(row.get("유통기한"))

        bl_last4   = (bl[-4:] if len(bl) >= 4 else bl).replace("/", "_")
        expire_str = (expire.replace("-", "") if expire else "").replace("/", "_")
        doc_id     = f"{code}_{bl_last4}_{expire_str}"

        if not doc_id or doc_id == "__":
            continue

        data = {
            "id":     doc_id,
            "pk":     doc_id,
            "상품명": to_str(row.get("수탁품", "")).strip(),
            "브랜드": to_str(row.get("브랜드", "")).strip(),
            "등급":   to_str(row.get("등급", "")).strip(),
            "ESTNO":  to_str(row.get("ESTNO", "")).strip(),
            "재고":   to_int(row.get("재고수량")),
            "BL":     bl,
            "창고":   to_str(row.get("창고", "")).strip(),
            "유통기한": expire,
            "중량":   to_float(row.get("중량")),
            "평중":   to_float(row.get("평균중량", "")),
            "출고일": to_date(row.get("출고일")),
            "홀딩":   to_str(row.get("홀딩", "")),
            "수집일": today,
            "상태":   "없음",
            "메모":   "",
        }
        if doc_id in result:
            # pk 충돌(코드+BL뒤4자리+유통기한 동일): 재고 합산
            result[doc_id]["재고"] = (result[doc_id].get("재고") or 0) + (data.get("재고") or 0)
        else:
            result[doc_id] = data
    return result


def _batch_upsert(db, items: dict):
    keys = list(items.keys())
    for i in range(0, len(keys), BATCH_LIMIT):
        batch = db.batch()
        for pk in keys[i:i + BATCH_LIMIT]:
            batch.set(db.collection(COLLECTION).document(pk), items[pk])
        batch.commit()


def _batch_delete(db, pks: list):
    for i in range(0, len(pks), BATCH_LIMIT):
        batch = db.batch()
        for pk in pks[i:i + BATCH_LIMIT]:
            batch.delete(db.collection(COLLECTION).document(pk))
        batch.commit()


class FirestoreUpdater:
    def __init__(self):
        _load_active_state()
        log.info(f"FirestoreUpdater 시작 - 활성 DB: {_active.upper()}")

    def update_diff(self, new_df: pd.DataFrame, prev_snapshot: dict) -> tuple:
        today    = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        new_data = _df_to_dict(new_df, today)

        to_upsert = {}
        to_delete = []

        for pk, data in new_data.items():
            prev = prev_snapshot.get(pk)
            if prev is None or _row_sig(prev) != _row_sig(data):
                to_upsert[pk] = data

        for pk in prev_snapshot:
            if pk not in new_data:
                to_delete.append(pk)

        total = len(to_upsert) + len(to_delete)

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
        db = _get_primary_db() if _active == "primary" else (
            _get_secondary_db() or _get_primary_db()
        )
        try:
            if to_upsert:
                _batch_upsert(db, to_upsert)
            if to_delete:
                _batch_delete(db, to_delete)
            log.info(f"  [{_active.upper()}] ↑{len(to_upsert)}건 / ✕{len(to_delete)}건")
            return total, new_data

        except Exception as e:
            if not _is_quota_error(e):
                raise
            log.warning(f"  [{_active.upper()}] 할당량 초과")
            return self._fallback_to_secondary(new_data, prev_snapshot)

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
            _batch_upsert(sec, new_data)
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
                _batch_upsert(pri, new_data)
            if to_delete:
                _batch_delete(pri, to_delete)
            _activate_primary()
            log.info(f"  [PRIMARY] 복귀 성공 - {len(new_data)}건 동기화 / {len(to_delete)}건 삭제")
            return True
        except Exception as e:
            if _is_quota_error(e):
                log.info("  Primary 아직 할당량 초과 - Secondary 유지")
            else:
                log.error(f"  Primary 복귀 오류: {e}")
            return False
