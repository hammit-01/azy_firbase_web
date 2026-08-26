"""FastAPI 서버 - 프론트엔드 ↔ MySQL CRUD."""
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import Any
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pipeline.mysql_db import (
    get_conn, sync_freeze, sync_estno_prefix, log_change, log_activity,
    upsert_inventory, delete_inventory,
    upsert_holding_record, delete_holding_record,
    upsert_azy_inventory, delete_azy_inventory,
    upsert_azy_holding_record, delete_azy_holding_record,
    create_reservation, cancel_reservation, complete_reservation, use_reservation,
    reactivate_reservation, update_reservation,
    get_active_reservations_by_pk, get_all_active_reservations,
    migrate_due_reservations_to_outbound, get_all_outbound, get_order_sheet_rows, create_outbound,
    update_outbound, cancel_outbound, use_outbound, toggle_outbound_complete,
    toggle_outbound_register, toggle_outbound_stock_release,
    toggle_outbound_slip, toggle_outbound_delivery_cancel,
    register_outbound_from_reservation, _today_iso,
    get_all_prices, create_price, update_price, delete_price,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 정적 파일(html/js/css)에 Cache-Control 헤더가 없으면 브라우저가 자체적으로
# 유효기간을 추측해서 캐싱한다(특히 모바일 Safari 즐겨찾기/홈화면 추가가 공격적으로
# 캐싱함) — 코드를 배포해도 기기가 옛 HTML/JS 조합을 계속 쓰면서 "로그인도 안 되고
# 아무것도 안 뜨는" 증상으로 나타남(2026-08-24). 매번 새로 받게 강제.
@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# ── 데이터 조회 ──────────────────────────────────────────────

@app.get("/api/inventory")
def get_inventory():
    """가용재고는 저장해두지 않고 조회 시점에 "실재고 − ACTIVE 예약 합계 −
    ACTIVE outbound 합계"로 계산한다(2026-08-05 재설계, 2026-08-14 outbound
    반영) — 예약을 아무리 잘못 만들어도 실재고(원본) 자체는 항상 정확하고,
    화면에 보여줄 값만 매번 다시 계산되므로 어긋난 채로 굳어질 수 없다.
    화면의 "예약" 열(예약수량)은 예약재고 + 당일출고재고(2026-08-14)."""
    today = _today_iso()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.*, COALESCE(r.예약재고, 0) + COALESCE(ob_today.당일출고재고, 0) AS 예약수량, "
                "i.재고 - COALESCE(r.예약재고, 0) - COALESCE(ob.출고수량, 0) AS 가용재고 "
                "FROM inventory i "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 예약재고 FROM holding_records "
                "           WHERE status='ACTIVE' GROUP BY pk) r ON i.id = r.pk "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 출고수량 FROM outbound "
                "           WHERE status='ACTIVE' GROUP BY pk) ob ON i.id = ob.pk "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 당일출고재고 FROM outbound "
                "           WHERE status='ACTIVE' AND 출고일=%s GROUP BY pk) ob_today ON i.id = ob_today.pk "
                "ORDER BY i.상품명, i.브랜드, i.등급",
                (today,),
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
            cur.execute("SELECT id, 이름, 권한, 부서, 직급 FROM employees WHERE id=%s AND pw=%s", (body.id, body.pw))
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


# ── 활동 로그(activity_log, 2026-08-18) — changes_log와 별개, 사이트 전체 CRUD를
# user_id 필수로 남기는 감사 로그. 재고장(inventory/azy_inventory/holding_records)
# 부터 우선 연결 — 예약/출고 탭은 추후.
class ActivityLogBody(BaseModel):
    user_id: str  # 필수 — 비어 있으면 Pydantic이 422로 거부
    user_name: str = ""
    action: str
    table_name: str
    record_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    summary: str = ""

@app.post("/api/activity_log")
def log_activity_endpoint(body: ActivityLogBody):
    if not body.user_id.strip():
        raise HTTPException(400, "user_id는 필수입니다")
    with get_conn() as conn:
        log_activity(
            conn, body.user_id, body.action, body.table_name, body.record_id,
            before=body.before, after=body.after, summary=body.summary, user_name=body.user_name,
        )
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
    """가용재고는 조회 시점 계산(get_inventory와 동일 원칙 — 2026-08-05 재설계,
    2026-08-14 outbound 반영). "예약" 열은 예약재고 + 당일출고재고."""
    today = _today_iso()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.*, COALESCE(r.예약재고, 0) + COALESCE(ob_today.당일출고재고, 0) AS 예약수량, "
                "i.재고 - COALESCE(r.예약재고, 0) - COALESCE(ob.출고수량, 0) AS 가용재고 "
                "FROM azy_inventory i "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 예약재고 FROM azy_holding_records "
                "           WHERE status='ACTIVE' GROUP BY pk) r ON i.id = r.pk "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 출고수량 FROM outbound "
                "           WHERE status='ACTIVE' GROUP BY pk) ob ON i.id = ob.pk "
                "LEFT JOIN (SELECT pk, CAST(SUM(수량) AS SIGNED) AS 당일출고재고 FROM outbound "
                "           WHERE status='ACTIVE' AND 출고일=%s GROUP BY pk) ob_today ON i.id = ob_today.pk "
                "ORDER BY i.상품명, i.브랜드, i.등급",
                (today,),
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
    상태:   str = ""  # 재고 매칭 조건에 포함(2026-08-21) — 선언 안 해두면 pydantic이
                       # 프론트에서 보낸 상태 필드를 조용히 버려서 매칭이 늘 실패했음
    수량:   int
    거래처: str = ""
    담당자: str = ""
    출고일: str = ""
    비고:   str = ""  # outbound 전용 컬럼(2026-08-19) — /api/reservations 쪽은 create_reservation이 무시

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


@app.post("/api/reservations/{rec_id}/reactivate")
def reactivate_reservation_endpoint(rec_id: str):
    with get_conn() as conn:
        ok = reactivate_reservation(conn, rec_id)
    if not ok:
        raise HTTPException(404, "완료 처리된 예약을 찾을 수 없습니다")
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


class UpdateReservationBody(BaseModel):
    수량: int | None = None
    출고일: str | None = None
    거래처: str | None = None
    전달사항: str | None = None
    비고: str | None = None

@app.post("/api/reservations/{rec_id}/update")
def update_reservation_endpoint(rec_id: str, body: UpdateReservationBody):
    updates = body.dict(exclude_unset=True)
    with get_conn() as conn:
        try:
            ok = update_reservation(conn, rec_id, updates)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "예약을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


class RegisterOutboundBody(BaseModel):
    수량: int
    출고일: str | None = None
    거래처: str | None = None

@app.post("/api/reservations/{rec_id}/register_outbound")
def register_outbound_endpoint(rec_id: str, body: RegisterOutboundBody):
    with get_conn() as conn:
        try:
            result = register_outbound_from_reservation(
                conn, rec_id, body.수량, body.출고일 or "", body.거래처 or ""
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
    return result


# ── outbound(타창고매출현황) — 예약과 완전히 분리된 별도 저장소(2026-08-14) ──
# 예약 중 출고일=오늘인 것은 outbound로 이동되고, sales.html은 이 API만 쓴다.

@app.get("/api/outbound")
def list_outbound():
    with get_conn() as conn:
        migrate_due_reservations_to_outbound(conn)
        rows = get_all_outbound(conn)
    return {"data": rows}


@app.get("/api/order_sheet")
def list_order_sheet():
    with get_conn() as conn:
        migrate_due_reservations_to_outbound(conn)
        rows = get_order_sheet_rows(conn)
    return {"data": rows}


@app.post("/api/outbound")
def create_outbound_endpoint(body: ReservationBody):
    with get_conn() as conn:
        try:
            rec = create_outbound(conn, body.dict())
        except ValueError as e:
            raise HTTPException(400, str(e))
    return rec


class UpdateOutboundBody(BaseModel):
    수량: int | None = None
    출고일: str | None = None
    거래처: str | None = None
    전달사항: str | None = None
    비고: str | None = None

@app.post("/api/outbound/{rec_id}/update")
def update_outbound_endpoint(rec_id: str, body: UpdateOutboundBody):
    updates = body.dict(exclude_unset=True)
    with get_conn() as conn:
        try:
            ok = update_outbound(conn, rec_id, updates)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "항목을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


@app.post("/api/outbound/{rec_id}/cancel")
def cancel_outbound_endpoint(rec_id: str, delete: bool = False):
    with get_conn() as conn:
        try:
            ok = cancel_outbound(conn, rec_id, delete)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "항목을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


@app.post("/api/outbound/{rec_id}/toggle_complete")
def toggle_outbound_complete_endpoint(rec_id: str):
    with get_conn() as conn:
        try:
            new_status = toggle_outbound_complete(conn, rec_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"status": new_status}


@app.post("/api/outbound/{rec_id}/toggle_register")
def toggle_outbound_register_endpoint(rec_id: str, body: dict[str, Any] = {}):
    user_name = body.get("담당자") or ""
    with get_conn() as conn:
        try:
            registered = toggle_outbound_register(conn, rec_id, user_name)
        except ValueError as e:
            raise HTTPException(404, str(e))
    return {"등록": registered}


@app.post("/api/outbound/{rec_id}/toggle_stock_release")
def toggle_outbound_stock_release_endpoint(rec_id: str):
    with get_conn() as conn:
        try:
            released = toggle_outbound_stock_release(conn, rec_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"수량내림": released}


@app.post("/api/outbound/{rec_id}/toggle_slip")
def toggle_outbound_slip_endpoint(rec_id: str):
    with get_conn() as conn:
        try:
            slip = toggle_outbound_slip(conn, rec_id)
        except ValueError as e:
            raise HTTPException(404, str(e))
    return {"전표": slip}


@app.post("/api/outbound/{rec_id}/toggle_delivery_cancel")
def toggle_outbound_delivery_cancel_endpoint(rec_id: str):
    with get_conn() as conn:
        try:
            cancelled = toggle_outbound_delivery_cancel(conn, rec_id)
        except ValueError as e:
            raise HTTPException(404, str(e))
    return {"배송취소": cancelled}


class UseOutboundBody(BaseModel):
    수량: int

@app.post("/api/outbound/{rec_id}/use")
def use_outbound_endpoint(rec_id: str, body: UseOutboundBody):
    with get_conn() as conn:
        try:
            ok = use_outbound(conn, rec_id, body.수량)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "항목을 찾을 수 없거나 이미 종료됨")
    return {"ok": True}


# ── 전략단가(price, 2026-08-19) ───────────────────────────────
class PriceBody(BaseModel):
    # 모든 칸이 비어 있어도 추가 가능해야 해서(2026-08-26) str 필드도 None을
    # 허용 — 프론트가 빈 입력칸을 null로 보내는데 기존 str-only 타입이 이를
    # 거부(422)해 추가 자체가 조용히 실패하던 버그였음.
    분류: str | None = None
    브랜드: str | None = None
    품목: str | None = None
    등급_포장: str | None = Field(None, alias="등급/포장")
    EST: str | None = None
    창고_비고: str | None = Field(None, alias="창고/비고")
    평중: float | None = None
    도매가: int | None = None
    전략가: int | None = None
    업데이트일자: str | None = None

    class Config:
        populate_by_name = True

@app.get("/api/price")
def list_prices():
    with get_conn() as conn:
        rows = get_all_prices(conn)
    return {"data": rows}


@app.post("/api/price")
def create_price_endpoint(body: PriceBody):
    row = body.dict(by_alias=True)
    with get_conn() as conn:
        new_id = create_price(conn, row)
    return {"id": new_id}


@app.put("/api/price/{price_id}")
def update_price_endpoint(price_id: str, body: dict[str, Any]):
    with get_conn() as conn:
        ok = update_price(conn, price_id, body)
    if not ok:
        raise HTTPException(404, "항목을 찾을 수 없음")
    return {"ok": True}


@app.delete("/api/price/{price_id}")
def delete_price_endpoint(price_id: str):
    with get_conn() as conn:
        ok = delete_price(conn, price_id)
    if not ok:
        raise HTTPException(404, "항목을 찾을 수 없음")
    return {"ok": True}


# ── 정적 파일 (프론트엔드) ───────────────────────────────────
@app.get("/")
def root():
    return RedirectResponse(url="/warehouse_main.html")

app.mount("/", StaticFiles(directory="front_end/html", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
