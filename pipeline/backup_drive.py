"""매시간 4개 탭(재고장/예약현황/타창고매출현황/단가표) 엑셀 백업 → 이동식 디스크(D:).

같은 파일명 덮어쓰기로 최신본 4개만 유지한다(폴더가 무한히 안 쌓이도록).
Google Drive API가 계속 SERVICE_DISABLED로 막혀서(2026-09-09) 이동식 디스크
로컬 저장으로 전환 — 이동식 디스크가 꽂혀있지 않으면 이번 회차만 실패하고
스케줄러가 다음 정각에 재시도한다(run_drive_backup의 try/except가 이미 감쌈).
"""
import logging
from pathlib import Path

import pandas as pd

from pipeline.mysql_db import (
    get_conn, get_all_active_reservations, get_all_outbound, get_all_prices,
    migrate_due_reservations_to_outbound, _today_iso,
)

log = logging.getLogger("backup_drive")

BACKUP_DIR = Path(r"D:\azy_warehouse_server_backup")

_INVENTORY_SQL = """
    SELECT i.*, COALESCE(r.예약재고, 0) + COALESCE(ob_today.당일출고재고, 0) AS 예약수량,
           i.재고 - COALESCE(r.예약재고, 0) - COALESCE(ob.출고수량, 0) AS 가용재고
    FROM {inv} i
    LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 예약재고 FROM {hold}
               WHERE status='ACTIVE' GROUP BY pk) r ON i.id = r.pk
    LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 출고수량 FROM outbound
               WHERE status='ACTIVE' GROUP BY pk) ob ON i.id = ob.pk
    LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 당일출고재고 FROM outbound
               WHERE status='ACTIVE' AND 출고일=%s GROUP BY pk) ob_today ON i.id = ob_today.pk
    ORDER BY i.상품명, i.브랜드, i.등급
"""


def _fetch_inventory(conn) -> list[dict]:
    """재고장 = inventory(JNS/에이스) + azy_inventory(나머지 창고) 합본."""
    today = _today_iso()
    rows = []
    with conn.cursor() as cur:
        for inv, hold in (("inventory", "holding_records"), ("azy_inventory", "azy_holding_records")):
            cur.execute(_INVENTORY_SQL.format(inv=inv, hold=hold), (today,))
            rows.extend(cur.fetchall())
    return rows


def run_backup() -> None:
    if not BACKUP_DIR.parent.exists():
        raise RuntimeError(f"백업 드라이브 미연결: {BACKUP_DIR.parent} 없음 — 이동식 디스크 꽂혀있는지 확인")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    with get_conn() as conn:
        migrate_due_reservations_to_outbound(conn)
        datasets = {
            "재고장.xlsx": _fetch_inventory(conn),
            "예약현황.xlsx": get_all_active_reservations(conn),
            "타창고매출현황.xlsx": get_all_outbound(conn),
            "단가표.xlsx": get_all_prices(conn),
        }

    for name, rows in datasets.items():
        pd.DataFrame(rows).to_excel(BACKUP_DIR / name, index=False)
        log.info(f"  [백업] {name} {len(rows)}행 저장 완료 → {BACKUP_DIR}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_backup()
