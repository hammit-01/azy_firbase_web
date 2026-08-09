"""FastAPI 서버 - 프론트엔드 ↔ MySQL CRUD."""
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Any
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pipeline.mysql_db import (
    get_conn, sync_freeze, sync_estno_prefix, log_change,
    upsert_inventory, delete_inventory,
    upsert_holding_record, delete_holding_record,
    upsert_azy_inventory, delete_azy_inventory,
    upsert_azy_holding_record, delete_azy_holding_record,
    create_reservation, cancel_reservation, complete_reservation, use_reservation,
    get_active_reservations_by_pk, get_all_active_reservations,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 데이터 조회 ──────────────────────────────────────────────

@app.get("/api/inventory")
def get_inventory():
    """가용재고는 저장해두지 않고 조회 시점에 "실재고 − ACTIVE 예약 합계"로 계산한다
    (2026-08-05 재설계) — 예약을 아무리 잘못 만들어도 실재고(원본) 자체는 항상
    정확하고, 화면에 보여줄 값만 매번 다시 계산되므로 어긋난 채로 굳어질 수 없다."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.*, COALESCE(r.예약수량, 0) AS 예약수량, "
                "i.재고 - COALESCE(r.예약수량, 0) AS 가용재고 "
                "FROM inventory i "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 예약수량 FROM holding_records "
                "           WHERE status='ACTIVE' GROUP BY pk) r ON i.id = r.pk "
                "ORDER BY i.상품명, i.브랜드, i.등급"
            )
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/yesterday_inventory")
def get_yesterday_inventory():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM yesterday_inventory")
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/employees")
def get_employees():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 이름, 권한 FROM employees ORDER BY 이름")
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/moving_inventory")
def get_moving_inventory():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM moving_inventory")
            rows = cur.fetchall()
    return {"data": rows}


class LoginBody(BaseModel):
    id: str
    pw: str

@app.post("/api/login")
def login(body: LoginBody):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, 이름, 권한 FROM employees WHERE id=%s AND pw=%s", (body.id, body.pw))
            row = cur.fetchone()
    if not row:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")
    return row


class ChangeLogBody(BaseModel):
    uid: str = ""
    target_table: str
    target_id: str
    action: str

@app.post("/api/changes_log")
def log_change_endpoint(body: ChangeLogBody):
    with get_conn() as conn:
        log_change(conn, body.uid, body.target_table, body.target_id, body.action)
    return {"ok": True}


# ── inventory CRUD ───────────────────────────────────────────

class ItemBody(BaseModel):
    data: dict[str, Any]

@app.post("/api/inventory")
def insert_item(body: ItemBody):
    row = body.data
    if not row.get("id"):
        row["id"] = str(uuid.uuid4())
    with get_conn() as conn:
        upsert_inventory(conn, [row])
    return {"id": row["id"]}


@app.put("/api/inventory/{item_id}")
def update_item(item_id: str, body: ItemBody):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM inventory WHERE id=%s", (item_id,))
            if not cur.fetchone():
                raise HTTPException(404, "not found")
        fields = body.data
        if not fields:
            raise HTTPException(400, "empty update")
        if "상품명" in fields:
            sync_freeze(fields)
        if "ESTNO" in fields:
            sync_estno_prefix(fields)
        set_clause = ", ".join([f"`{k}`=%s" for k in fields])
        cur_vals   = list(fields.values()) + [item_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE inventory SET {set_clause} WHERE id=%s", cur_vals)
    return {"ok": True}


@app.delete("/api/inventory/{item_id}")
def delete_item(item_id: str):
    with get_conn() as conn:
        # 홀딩 표시 행을 그냥 지우면 짝지어진 holding_records가 안 지워져서, 그 수량이
        # 매 사이클 정상 재고 계산(크롤원본-홀딩합계)에서 계속 빠진 채로 유령처럼 남는다
        # (2026-08-05, 실사용 중 20박스가 홀딩 표시도 정상 재고도 아닌 채로 사라진 사고
        # 발견). 삭제할 행이 홀딩 행이면 holding_records도 같이 지운다.
        with conn.cursor() as cur:
            cur.execute("SELECT holdingRecordId FROM inventory WHERE id=%s", (item_id,))
            row = cur.fetchone()
        delete_inventory(conn, [item_id])
        if row and row.get("holdingRecordId"):
            delete_holding_record(conn, row["holdingRecordId"])
    return {"ok": True}


# ── holding_records CRUD ─────────────────────────────────────

class HoldingBody(BaseModel):
    id:   str
    data: dict[str, Any]

@app.post("/api/holding_records")
def insert_holding(body: HoldingBody):
    rec = {"id": body.id, **body.data, "홀딩일자": datetime.now().strftime("%Y.%m.%d")}
    with get_conn() as conn:
        upsert_holding_record(conn, rec)
    return {"id": body.id}


@app.put("/api/holding_records/{rec_id}")
def update_holding(rec_id: str, body: ItemBody):
    with get_conn() as conn:
        fields = body.data
        set_clause = ", ".join([f"`{k}`=%s" for k in fields])
        vals = list(fields.values()) + [rec_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE holding_records SET {set_clause} WHERE id=%s", vals)
    return {"ok": True}


@app.delete("/api/holding_records/{rec_id}")
def delete_holding(rec_id: str):
    with get_conn() as conn:
        delete_holding_record(conn, rec_id)
    return {"ok": True}


@app.get("/api/holding_records_detail/{rec_id}")
def get_holding_detail(rec_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM holding_records WHERE id=%s", (rec_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "not found")
    return {"data": row}


@app.get("/api/holding_records/count/{pk}")
def count_holding_by_pk(pk: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM holding_records WHERE pk=%s", (pk,))
            row = cur.fetchone()
    return {"count": row["cnt"]}


# ── 타창고(azy) inventory ────────────────────────────────────

@app.get("/api/azy_inventory")
def get_azy_inventory():
    """가용재고는 조회 시점 계산(get_inventory와 동일 원칙 — 2026-08-05 재설계)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.*, COALESCE(r.예약수량, 0) AS 예약수량, "
                "i.재고 - COALESCE(r.예약수량, 0) AS 가용재고 "
                "FROM azy_inventory i "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 예약수량 FROM azy_holding_records "
                "           WHERE status='ACTIVE' GROUP BY pk) r ON i.id = r.pk "
                "ORDER BY i.상품명, i.브랜드, i.등급"
            )
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/yesterday_azy_inventory")
def get_yesterday_azy_inventory():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM yesterday_azy_inventory")
            rows = cur.fetchall()
    return {"data": rows}


@app.post("/api/azy_inventory")
def insert_azy_item(body: ItemBody):
    row = body.data
    if not row.get("id"):
        row["id"] = str(uuid.uuid4())
    with get_conn() as conn:
        upsert_azy_inventory(conn, [row])
    return {"id": row["id"]}


@app.put("/api/azy_inventory/{item_id}")
def update_azy_item(item_id: str, body: ItemBody):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM azy_inventory WHERE id=%s", (item_id,))
            if not cur.fetchone():
                raise HTTPException(404, "not found")
        fields = body.data
        if not fields:
            raise HTTPException(400, "empty update")
        if "상품명" in fields:
            sync_freeze(fields)
        if "ESTNO" in fields:
            sync_estno_prefix(fields)
        set_clause = ", ".join([f"`{k}`=%s" for k in fields])
        cur_vals   = list(fields.values()) + [item_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE azy_inventory SET {set_clause} WHERE id=%s", cur_vals)
    return {"ok": True}


@app.delete("/api/azy_inventory/{item_id}")
def delete_azy_item(item_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT holdingRecordId FROM azy_inventory WHERE id=%s", (item_id,))
            row = cur.fetchone()
        delete_azy_inventory(conn, [item_id])
        if row and row.get("holdingRecordId"):
            delete_azy_holding_record(conn, row["holdingRecordId"])
    return {"ok": True}


# ── 타창고(azy) holding_records ──────────────────────────────

@app.post("/api/azy_holding_records")
def insert_azy_holding(body: HoldingBody):
    rec = {"id": body.id, **body.data, "홀딩일자": datetime.now().strftime("%Y.%m.%d")}
    with get_conn() as conn:
        upsert_azy_holding_record(conn, rec)
    return {"id": body.id}


@app.put("/api/azy_holding_records/{rec_id}")
def update_azy_holding(rec_id: str, body: ItemBody):
    with get_conn() as conn:
        fields = body.data
        set_clause = ", ".join([f"`{k}`=%s" for k in fields])
        vals = list(fields.values()) + [rec_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE azy_holding_records SET {set_clause} WHERE id=%s", vals)
    return {"ok": True}


@app.delete("/api/azy_holding_records/{rec_id}")
def delete_azy_holding(rec_id: str):
    with get_conn() as conn:
        delete_azy_holding_record(conn, rec_id)
    return {"ok": True}


@app.get("/api/azy_holding_records_detail/{rec_id}")
def get_azy_holding_detail(rec_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM azy_holding_records WHERE id=%s", (rec_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "not found")
    return {"data": row}


@app.get("/api/azy_holding_records/count/{pk}")
def count_azy_holding_by_pk(pk: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM azy_holding_records WHERE pk=%s", (pk,))
            row = cur.fetchone()
    return {"count": row["cnt"]}


# ── 예약(홀딩) — 실재고/예약 분리 재설계(2026-08-05) ──────────
# 소스 재고는 절대 건드리지 않고 holding_records/azy_holding_records에만 쌓는다.
# 취소/완료도 물리 삭제 대신 status 변경 — 삭제 시 짝지어진 데이터가 안 지워져
# 재고가 유령처럼 사라지던 사고(2026-08-05)를 구조적으로 막기 위함.

class ReservationBody(BaseModel):
    상품명: str
    브랜드: str = ""
    등급:   str = ""
    ESTNO:  str = ""
    BL:     str
    창고:   str
    수량:   int
    거래처: str = ""
    담당자: str = ""
    출고일: str = ""

@app.get("/api/reservations")
def list_all_reservations():
    with get_conn() as conn:
        rows = get_all_active_reservations(conn)
    return {"data": rows}


@app.get("/api/reservations/by_pk/{pk}")
def list_reservations_by_pk(pk: str):
    with get_conn() as conn:
        rows = get_active_reservations_by_pk(conn, pk)
    return {"data": rows}


@app.post("/api/reservations")
def create_reservation_endpoint(body: ReservationBody):
    with get_conn() as conn:
        try:
            rec = create_reservation(conn, body.dict())
        except ValueError as e:
            raise HTTPException(400, str(e))
    return rec


@app.post("/api/reservations/{rec_id}/cancel")
def cancel_reservation_endpoint(rec_id: str):
    with get_conn() as conn:
        ok = cancel_reservation(conn, rec_id)
    if not ok:
        raise HTTPException(404, "예약을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


@app.post("/api/reservations/{rec_id}/complete")
def complete_reservation_endpoint(rec_id: str):
    with get_conn() as conn:
        ok = complete_reservation(conn, rec_id)
    if not ok:
        raise HTTPException(404, "예약을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


class UseReservationBody(BaseModel):
    수량: int

@app.post("/api/reservations/{rec_id}/use")
def use_reservation_endpoint(rec_id: str, body: UseReservationBody):
    with get_conn() as conn:
        try:
            ok = use_reservation(conn, rec_id, body.수량)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "예약을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


# ── 정적 파일 (프론트엔드) ───────────────────────────────────
@app.get("/")
def root():
    return RedirectResponse(url="/warehouse_main.html")

app.mount("/", StaticFiles(directory="front_end/html", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
