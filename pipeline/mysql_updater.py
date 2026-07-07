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
        self._write_pending_changes(pending_list)  # 항상 호출 — 빈 list면 DELETE만

        self._flag_holding_issues(holding_sum, crawled_key_totals)

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

    def _flag_holding_issues(self, holding_sum: dict, crawled_key_totals: dict):
        """수량초과·원본없음 홀딩 행 자동 처리 — UI 수동 개입 불필요."""
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, pk, `재고`, holdingRecordId FROM inventory "
                        "WHERE `수집일`='' AND `상태`='holding'"
                    )
                    holding_rows = cur.fetchall()

            # pk → [rows] 그룹핑
            rows_by_pk: dict = {}
            for row in holding_rows:
                rows_by_pk.setdefault(row["pk"] or "", []).append(row)

            with get_conn() as conn:
                for pk, rows in rows_by_pk.items():
                    if not pk:
                        continue
                    h_total = holding_sum.get(pk, 0)
                    crawled = crawled_key_totals.get(pk, 0)

                    if crawled == 0:
                        # 원본없음: 크롤에서 완전히 사라진 항목 → 홀딩 row + records 삭제
                        for row in rows:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM inventory WHERE id=%s", (row["id"],))
                                if row["holdingRecordId"]:
                                    cur.execute("DELETE FROM holding_records WHERE id=%s",
                                                (row["holdingRecordId"],))
                        log.info(f"  [홀딩이상-자동] 원본없음 pk={pk[:25]} → {len(rows)}건 삭제")

                    elif h_total > crawled:
                        # 수량초과: 초과분(h_total - crawled)을 작은 row부터 차감
                        excess = h_total - crawled
                        remaining = excess
                        for row in sorted(rows, key=lambda r: r["재고"] or 0):
                            if remaining <= 0:
                                break
                            cur_qty = row["재고"] or 0
                            reduce  = min(cur_qty, remaining)
                            new_qty = cur_qty - reduce
                            with conn.cursor() as cur:
                                if new_qty <= 0:
                                    cur.execute("DELETE FROM inventory WHERE id=%s", (row["id"],))
                                    if row["holdingRecordId"]:
                                        cur.execute("DELETE FROM holding_records WHERE id=%s",
                                                    (row["holdingRecordId"],))
                                else:
                                    cur.execute(
                                        "UPDATE inventory SET `재고`=%s WHERE id=%s",
                                        (new_qty, row["id"])
                                    )
                                    if row["holdingRecordId"]:
                                        cur.execute(
                                            "UPDATE holding_records SET `수량`=%s WHERE id=%s",
                                            (new_qty, row["holdingRecordId"])
                                        )
                            remaining -= reduce
                        log.info(f"  [홀딩이상-자동] 수량초과 pk={pk[:25]} → -{excess}박스 차감")

        except Exception as e:
            log.warning(f"  홀딩 이상 자동처리 실패: {e}")

    def _write_pending_changes(self, pending_list: dict):
        import json
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    # 매 사이클마다 전체 교체 — 해소된 항목 자동 삭제
                    cur.execute("DELETE FROM pending_changes")
                    for pk, info in pending_list.items():
                        cur.execute(
                            "INSERT INTO pending_changes (id, data_json) VALUES (%s, %s)",
                            (pk, json.dumps(info, ensure_ascii=False))
                        )
            log.info(f"  [pending] {len(pending_list)}건 기록")
        except Exception as e:
            log.warning(f"  pending 기록 실패: {e}")
