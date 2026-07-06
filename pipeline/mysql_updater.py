"""MySQL 기반 재고 업데이터."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.mysql_db import (
    get_conn, upsert_inventory, delete_inventory,
    get_holding_sum, get_holding_records_by_key,
    get_holding_rows_by_bl, get_employees, get_snapshot,
)
from pipeline.updater import _df_to_dict, _row_sig

log = logging.getLogger("mysql_updater")


class MySQLUpdater:
    def update_diff(self, new_df, prev_snapshot: dict) -> tuple:
        """
        prev_snapshot (pickle): 마지막 파이프라인 실행 시점 상태 → _df_to_dict 비교용
        db_snapshot (MySQL):    현재 DB 실제 상태              → INSERT/UPDATE/DELETE 결정용

        두 snapshot을 분리해야 홀딩 후 파이프라인이 "재고증가"로 오인식하지 않음.
        """
        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")

        with get_conn() as conn:
            holding_sum            = get_holding_sum(conn)
            holding_records_by_key = get_holding_records_by_key(conn)
            holding_rows_by_bl     = get_holding_rows_by_bl(conn)
            employees_names        = get_employees(conn)
            db_snapshot            = get_snapshot(conn)  # 현재 MySQL 상태

        if holding_sum:
            log.info(f"  홀딩 데이터 {len(holding_sum)}건 / BL인덱스 {len(holding_rows_by_bl)}건 조회 완료")

        # 첫 실행(MySQL 비어 있음): pickle도 비워서 전량 INSERT 유도
        if not db_snapshot:
            prev_snapshot = {}

        try:
            from pipeline.sheets_reader import load_sheet_records
            sheet_records = load_sheet_records()
        except Exception as e:
            log.warning(f"  시트 로드 실패: {e}")
            sheet_records = {}

        # _df_to_dict: pickle prev_snapshot 기준으로 재고 증감 감지
        new_data, crawled_key_totals, pending_list, auto_list = _df_to_dict(
            new_df, today, holding_sum, prev_snapshot,
            holding_rows_by_bl=holding_rows_by_bl,
            holding_records_by_key=holding_records_by_key,
            sheet_records=sheet_records,
            employees_names=employees_names,
        )

        # INSERT/UPDATE/DELETE: db_snapshot(현재 MySQL) 기준으로 결정
        to_insert = {}
        to_update = {}
        to_delete = []

        for pk, data in new_data.items():
            db_prev = db_snapshot.get(pk)
            if db_prev is None:
                to_insert[pk] = {**data, "홀딩": "", "상태": "없음", "메모": ""}
            elif _row_sig(db_prev) != _row_sig(data):
                to_update[pk] = data

        for pk in db_snapshot:
            if pk not in new_data:
                to_delete.append(pk)

        total = len(to_insert) + len(to_update) + len(to_delete)

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

        if auto_list:
            self._apply_auto_deductions(auto_list)
        if pending_list:
            self._write_pending_changes(pending_list)

        return total, new_data

    def _apply_auto_deductions(self, auto_list: dict):
        try:
            with get_conn() as conn:
                for pk, info in auto_list.items():
                    diff = info["diff"]
                    remaining = diff
                    for row in sorted(info["matched_rows"], key=lambda r: r["qty"], reverse=True):
                        if remaining <= 0:
                            break
                        deduct  = min(row["qty"], remaining)
                        new_qty = row["qty"] - deduct
                        with conn.cursor() as cur:
                            cur.execute("UPDATE inventory SET `재고`=%s WHERE id=%s",
                                        (new_qty, row["doc_id"]))
                        remaining -= deduct

                    remaining2 = diff
                    for rec in sorted(info["matched_records"], key=lambda r: r["qty"], reverse=True):
                        if remaining2 <= 0:
                            break
                        deduct  = min(rec["qty"], remaining2)
                        new_qty = rec["qty"] - deduct
                        with conn.cursor() as cur:
                            cur.execute("UPDATE holding_records SET `수량`=%s WHERE id=%s",
                                        (new_qty, rec["id"]))
                        remaining2 -= deduct
            log.info(f"  [자동차감] {len(auto_list)}건 처리")
        except Exception as e:
            log.warning(f"  자동차감 실패: {e}")

    def _write_pending_changes(self, pending_list: dict):
        import json
        try:
            with get_conn() as conn:
                for pk, info in pending_list.items():
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pending_changes (id, data_json) VALUES (%s, %s) "
                            "ON DUPLICATE KEY UPDATE data_json=%s",
                            (pk, json.dumps(info, ensure_ascii=False),
                                 json.dumps(info, ensure_ascii=False))
                        )
            log.info(f"  [pending] {len(pending_list)}건 기록")
        except Exception as e:
            log.warning(f"  pending 기록 실패: {e}")
