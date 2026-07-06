"""FastAPI 서버 - 프론트엔드 ↔ MySQL CRUD."""
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Any
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pipeline.mysql_db import get_conn, upsert_inventory, delete_inventory, upsert_holding_record, delete_holding_record

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
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM inventory ORDER BY 상품명, 브랜드, 등급")
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/employees")
def get_employees():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM employees ORDER BY 이름")
            rows = cur.fetchall()
    return {"data": rows}


@app.get("/api/pending_changes")
def get_pending_changes():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, data_json FROM pending_changes ORDER BY created_at DESC")
            rows = cur.fetchall()
    result = []
    for row in rows:
        item = {"id": row["id"]}
        if isinstance(row["data_json"], dict):
            item.update(row["data_json"])
        result.append(item)
    return {"data": result}


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
        set_clause = ", ".join([f"`{k}`=%s" for k in fields])
        cur_vals   = list(fields.values()) + [item_id]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE inventory SET {set_clause} WHERE id=%s", cur_vals)
    return {"ok": True}


@app.delete("/api/inventory/{item_id}")
def delete_item(item_id: str):
    with get_conn() as conn:
        delete_inventory(conn, [item_id])
    return {"ok": True}


# ── holding_records CRUD ─────────────────────────────────────

class HoldingBody(BaseModel):
    id:   str
    data: dict[str, Any]

@app.post("/api/holding_records")
def insert_holding(body: HoldingBody):
    rec = {"id": body.id, **body.data}
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


@app.delete("/api/pending_changes/{item_id}")
def delete_pending(item_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pending_changes WHERE id=%s", (item_id,))
    return {"ok": True}


@app.get("/api/holding_records/count/{pk}")
def count_holding_by_pk(pk: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM holding_records WHERE pk=%s", (pk,))
            row = cur.fetchone()
    return {"count": row["cnt"]}


# ── 정적 파일 (프론트엔드) ───────────────────────────────────
@app.get("/")
def root():
    return RedirectResponse(url="/warehouse_main.html")

app.mount("/", StaticFiles(directory="front_end/html", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
