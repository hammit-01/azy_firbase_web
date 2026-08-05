"""MySQL 기반 재고 업데이터."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.mysql_db import (
    get_conn, upsert_inventory, delete_inventory,
    get_holding_sum, get_snapshot,
    sync_freeze, sync_estno_prefix, sync_name_rename, sync_grade_clear, sync_field_fill,
)
from pipeline.updater import _df_to_dict, _row_sig

log = logging.getLogger("mysql_updater")

# 사용자가 UI에서 직접 고칠 수 있는 마스터 필드 — 기존 행이면 크롤값으로 덮어쓰지 않고 보존
_PRESERVE_ON_UPDATE = ("상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "유통기한", "평중", "출고일")


class MySQLUpdater:
    def update_diff(self, new_df, prev_snapshot: dict) -> tuple:
        """
        prev_snapshot (pickle): 마지막 파이프라인 실행 시점 상태 → _df_to_dict 비교용
        db_snapshot (MySQL):    현재 DB 실제 상태              → INSERT/UPDATE/DELETE 결정용

        예약(홀딩) 시스템 재설계(2026-08-05) 이후, 크롤러는 실재고만 반영한다.
        재고 감소가 예약 소진 때문인지 일반 출고인지는 여기서 판단하지 않는다 —
        가용재고는 API가 조회 시점에 "실재고 − ACTIVE 예약 합계"로 계산한다.
        """
        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

        with get_conn() as conn:
            holding_sum = get_holding_sum(conn)  # holdingTotal 참고용 스냅샷에만 사용
            db_snapshot = get_snapshot(conn)     # 현재 MySQL 상태

        # 첫 실행(MySQL 비어 있음): pickle도 비워서 전량 INSERT 유도
        if not db_snapshot:
            prev_snapshot = {}

        new_data = _df_to_dict(new_df, today, holding_sum)

        # INSERT/UPDATE/DELETE: db_snapshot(현재 MySQL) 기준으로 결정
        to_insert = {}
        to_update = {}
        to_delete = []

        for pk, data in new_data.items():
            # ESTNO 강제규칙/상품명 치환규칙은 원래 upsert_inventory()에서 DB 쓰기 직전에만
            # 적용됐는데, 그러면 크롤 원본(예: ESTNO "103")과 저장값(규칙 적용된 "ME103")이
            # 매 사이클 달라 보여서 아래 _row_sig 비교가 영원히 "변경"으로 오판정하고 매번
            # 헛돌며 재기록했다 — 비교 전에 먼저 규칙을 적용해 원본 쪽도 최종값으로 맞춘다
            # (2026-07-31, [진단-트리거] 로그로 확인).
            data = sync_field_fill(sync_grade_clear(sync_name_rename(sync_estno_prefix(sync_freeze(data)))))
            db_prev = db_snapshot.get(pk)
            if db_prev is None:
                # 신규 행: 파손/상이품/반품·필수값 결측 자동 감지 결과를 초기 상태로 사용
                auto_state = data.get("_auto_상태", "")
                auto_memo  = data.get("_auto_메모", "")
                to_insert[pk] = {**data, "홀딩": "", "상태": auto_state or "없음", "메모": auto_memo}
            elif _row_sig(db_prev) != _row_sig(data):
                merged = {**data}
                for f in _PRESERVE_ON_UPDATE:
                    # db_prev 값이 비어있으면 보존하지 않고 새 크롤/파싱 결과를 그대로 씀 —
                    # 안 그러면 원래 비어있거나 잘못 들어간 값이 영원히 안 고쳐짐
                    # (2026-07-29, eda_standard 파싱 개선이 기존 행엔 전혀 안 먹던 사고).
                    if db_prev.get(f) not in (None, ""):
                        merged[f] = db_prev[f]
                merged["홀딩"] = db_prev.get("홀딩", "")
                merged["상태"] = db_prev.get("상태", "없음")
                merged["메모"] = db_prev.get("메모", "")
                # 실재고가 실제로 바뀐 경우에만 버전 증가 — 예약 화면에서 "예약 당시
                # 버전과 다르면 재고가 바뀐 것"을 판단하는 기준이라, 홀딩total 같은
                # 참고용 필드만 바뀐 걸로는 올리면 안 됨.
                if (db_prev.get("재고") or 0) != (data.get("재고") or 0):
                    merged["stock_version"] = (db_prev.get("stock_version") or 0) + 1
                else:
                    merged["stock_version"] = db_prev.get("stock_version") or 0
                to_update[pk] = merged

        for pk in db_snapshot:
            if pk not in new_data:
                to_delete.append(pk)

        total = len(to_insert) + len(to_update) + len(to_delete)

        # 정보누락(null) 상태는 재고 증감과 무관하게 매 사이클 전체 행 기준으로 재계산
        # (홀딩/특이품으로 이미 표시된 행은 건드리지 않음)
        with get_conn() as conn:
            self._sync_missing_status(conn)

        if total == 0:
            log.info("  변경 없음")
            return 0, new_data

        with get_conn() as conn:
            if to_insert:
                upsert_inventory(conn, list(to_insert.values()))
            if to_update:
                upsert_inventory(conn, list(to_update.values()))
            if to_delete:
                delete_inventory(conn, to_delete)

        log.info(f"  [MYSQL] ↑{len(to_insert)}건(신규) ↻{len(to_update)}건(갱신) ✕{len(to_delete)}건")

        self._try_auto_complete(db_snapshot, new_data)

        return total, new_data

    def _try_auto_complete(self, db_snapshot: dict, new_data: dict):
        """실재고가 줄어든 항목 중, 출고 기록 시트에 근거가 있고(오늘 그 BL/ESTNO/등급
        출고가 실제로 기록됨) ACTIVE 예약과 수량까지 정확히 맞아떨어지는 경우에만
        자동으로 예약을 완료 처리한다. 애매하면(시트 근거 없음/예약 여러 건/수량 불일치)
        절대 자동으로 안 건드리고 그냥 넘어간다 — 크롤링 결과만으로 예약 상태를 바꾸지
        않는다는 원칙의 유일한 예외이며, 그래서 조건을 엄격하게 둔다(2026-08-05).
        JNS/곤 창고(holding_records)만 대상 — 출고 기록 시트가 그쪽 기준으로 운영됨."""
        try:
            from pipeline.sheets_reader import load_sheet_records
            from pipeline.mysql_db import try_auto_complete_by_shipment
            sheet_records = load_sheet_records()
        except Exception as e:
            log.warning(f"  출고 시트 로드 실패(자동완료 스킵): {e}")
            return
        if not sheet_records:
            return

        completed = 0
        with get_conn() as conn:
            for pk, data in new_data.items():
                prev = db_snapshot.get(pk)
                if not prev:
                    continue
                diff = (prev.get("재고") or 0) - (data.get("재고") or 0)
                if diff <= 0:
                    continue  # 재고 증가/동일 — 대상 아님

                bl, estno, grade = data.get("BL", ""), data.get("ESTNO", ""), data.get("등급", "")
                has_sheet_evidence = any(
                    e["estno"] == estno and e["grade"] == grade
                    for e in sheet_records.get(bl, [])
                )
                if not has_sheet_evidence:
                    continue

                if try_auto_complete_by_shipment(conn, bl, estno, grade, diff):
                    completed += 1

        if completed:
            log.info(f"  [자동완료] 출고 시트 대조로 예약 {completed}건 완료 처리")

    def _sync_missing_status(self, conn):
        """상품명/브랜드/등급/ESTNO 중 하나라도 비어있으면 상태=null, 다 채워지면 상태=없음으로
        되돌림. 메모에 "검품"이 남아있으면 상태=특이품으로 강제. 홀딩/동결 행은 건드리지 않음 —
        재고 증감 diff와 무관하게 매 사이클 실행."""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE inventory SET `상태`='null' "
                    "WHERE `상태` NOT IN ('holding', '특이품', 'null', 'freeze') "
                    "AND (`상품명`='' OR `브랜드`='' OR `등급`='' OR `ESTNO`='')"
                )
                cur.execute(
                    "UPDATE inventory SET `상태`='없음' "
                    "WHERE `상태`='null' "
                    "AND `상품명`!='' AND `브랜드`!='' AND `등급`!='' AND `ESTNO`!=''"
                )
                cur.execute(
                    "UPDATE inventory SET `상태`='특이품' "
                    "WHERE `상태` != 'holding' AND `상태` != '특이품' "
                    "AND `메모` LIKE '%검품%'"
                )
        except Exception as e:
            log.warning(f"  정보누락 상태 동기화 실패: {e}")
