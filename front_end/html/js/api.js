// api.js — MySQL 백엔드 API 클라이언트
const API_BASE = window.location.origin;

// azy가 명시되면 그 값을 쓰고, 아니면 페이지 전역 플래그(__AZY_API_MODE)를 따른다.
// 통관분 페이지에서 타창고 데이터를 함께 불러올 때 호출별로 azy=true를 넘겨 라우팅한다.
function _resolvePath(p, azy) {
    const useAzy = azy ?? window.__AZY_API_MODE;
    if (!useAzy) return p;
    return p
        .replace(/^\/api\/yesterday_inventory/, "/api/yesterday_azy_inventory")
        .replace(/^\/api\/inventory/, "/api/azy_inventory")
        .replace(/^\/api\/holding_records/, "/api/azy_holding_records");
}

export async function apiFetch(path, options = {}, azy) {
    const res = await fetch(`${API_BASE}${_resolvePath(path, azy)}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) {
        // FastAPI HTTPException은 {"detail": "사유"} 형태로 옴 — 있으면 그대로 보여준다
        // (예: 예약 생성 실패 시 "가용재고 부족(가용 42, 요청 47)"처럼 구체적인 사유).
        let detail = "";
        try { detail = (await res.json())?.detail || ""; } catch {}
        throw new Error(detail || `API ${path} 실패: ${res.status}`);
    }
    return res.json();
}

// ── 재고 조회 ──────────────────────────────────────────────

export async function fetchAllInventory(azy) {
    const r = await apiFetch("/api/inventory", {}, azy);
    return r.data;
}

export async function fetchYesterdayInventory(azy) {
    const r = await apiFetch("/api/yesterday_inventory", {}, azy);
    return r.data;
}

export async function fetchEmployees() {
    const r = await apiFetch("/api/employees");
    return r.data;
}

export async function fetchMovingInventory() {
    const r = await apiFetch("/api/moving_inventory");
    return r.data;
}

// 로그인 실패(401)는 흐름상 정상 케이스라 throw 없이 null로 반환
export async function apiLogin(id, pw) {
    const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, pw }),
    });
    if (!res.ok) return null;
    return res.json();
}

// 변경 이력 기록 — 실패해도 원래 하려던 작업(추가/수정/삭제/홀딩)을 막으면 안 되니 조용히 무시
export async function apiLogChange(uid, target_table, target_id, action) {
    try {
        await fetch(`${API_BASE}/api/changes_log`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uid: uid || "", target_table, target_id, action }),
        });
    } catch {}
}

// activity_log(2026-08-18) — user_id 없으면 서버가 400으로 거절하므로, 로그인 안 된
// 상태(user_id 없음)에서는 애초에 호출 안 함(호출부 _logActivity가 가드).
export async function apiLogActivity(entry) {
    try {
        await fetch(`${API_BASE}/api/activity_log`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(entry),
        });
    } catch {}
}

// ── inventory CRUD ─────────────────────────────────────────

export async function apiInsertItem(data, azy) {
    return apiFetch("/api/inventory", {
        method: "POST",
        body: JSON.stringify({ data }),
    }, azy);
}

export async function apiUpdateItem(id, fields, azy) {
    return apiFetch(`/api/inventory/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify({ data: fields }),
    }, azy);
}

export async function apiDeleteItem(id, azy) {
    return apiFetch(`/api/inventory/${encodeURIComponent(id)}`, {
        method: "DELETE",
    }, azy);
}

// ── holding_records CRUD ───────────────────────────────────
// (예약 생성/취소는 apiCreateReservation/apiCancelReservation으로 대체됨 — 아래
// update/delete는 옛 "상태를 holding으로 직접 수정" 편집 경로에서 아직 씀)

export async function apiUpdateHoldingRecord(id, fields, azy) {
    return apiFetch(`/api/holding_records/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify({ data: fields }),
    }, azy);
}

export async function apiDeleteHoldingRecord(id, azy) {
    return apiFetch(`/api/holding_records/${encodeURIComponent(id)}`, {
        method: "DELETE",
    }, azy);
}

// ── 예약(홀딩) — 실재고/예약 분리 재설계(2026-08-05) ──────────
// 서버가 창고명으로 inventory/azy_inventory를 알아서 판별하므로 azy 인자가 필요 없다.

export async function apiGetAllReservations() {
    const r = await apiFetch("/api/reservations", {});
    return r.data;
}

export async function apiGetReservationsByPk(pk) {
    const r = await apiFetch(`/api/reservations/by_pk/${encodeURIComponent(pk)}`, {});
    return r.data;
}

export async function apiCreateReservation(product) {
    return apiFetch("/api/reservations", {
        method: "POST",
        body: JSON.stringify(product),
    });
}

export async function apiCancelReservation(id) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/cancel`, { method: "POST" });
}

export async function apiCompleteReservation(id) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/complete`, { method: "POST" });
}

export async function apiUseReservation(id, qty) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/use`, {
        method: "POST",
        body: JSON.stringify({ 수량: qty }),
    });
}

export async function apiReactivateReservation(id) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/reactivate`, { method: "POST" });
}

export async function apiUpdateReservation(id, fields) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/update`, {
        method: "POST",
        body: JSON.stringify(fields),
    });
}

export async function apiRegisterOutboundFromReservation(id, { 수량, 출고일, 거래처 }) {
    return apiFetch(`/api/reservations/${encodeURIComponent(id)}/register_outbound`, {
        method: "POST",
        body: JSON.stringify({ 수량, 출고일, 거래처 }),
    });
}

// ── outbound(타창고매출현황) — 예약과 분리된 별도 저장소(2026-08-14) ──
export async function apiGetAllOutbound() {
    const r = await apiFetch("/api/outbound", {});
    return r.data;
}

export async function apiGetOrderSheet() {
    const r = await apiFetch("/api/order_sheet", {});
    return r.data;
}

export async function apiCreateOutbound(product) {
    return apiFetch("/api/outbound", {
        method: "POST",
        body: JSON.stringify(product),
    });
}

export async function apiUpdateOutbound(id, fields) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/update`, {
        method: "POST",
        body: JSON.stringify(fields),
    });
}

export async function apiCancelOutbound(id, deleteIt = false) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/cancel?delete=${deleteIt}`, { method: "POST" });
}

export async function apiUseOutbound(id, qty) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/use`, {
        method: "POST",
        body: JSON.stringify({ 수량: qty }),
    });
}

export async function apiToggleOutboundComplete(id) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/toggle_complete`, { method: "POST" });
}

export async function apiToggleOutboundRegister(id) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/toggle_register`, { method: "POST" });
}

export async function apiToggleOutboundStockRelease(id) {
    return apiFetch(`/api/outbound/${encodeURIComponent(id)}/toggle_stock_release`, { method: "POST" });
}

// ── 전략단가(price, 2026-08-19) ────────────────────────────────
export async function apiGetAllPrices() {
    const r = await apiFetch("/api/price", {});
    return r.data;
}

export async function apiCreatePrice(row) {
    return apiFetch("/api/price", { method: "POST", body: JSON.stringify(row) });
}

export async function apiUpdatePrice(id, fields) {
    return apiFetch(`/api/price/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(fields) });
}

export async function apiDeletePrice(id) {
    return apiFetch(`/api/price/${encodeURIComponent(id)}`, { method: "DELETE" });
}
