// api.js — MySQL 백엔드 API 클라이언트
const API_BASE = window.location.origin;

function _resolvePath(p) {
    if (!window.__AZY_API_MODE) return p;
    return p
        .replace(/^\/api\/inventory/, "/api/azy_inventory")
        .replace(/^\/api\/holding_records/, "/api/azy_holding_records");
}

export async function apiFetch(path, options = {}) {
    const res = await fetch(`${API_BASE}${_resolvePath(path)}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) throw new Error(`API ${path} 실패: ${res.status}`);
    return res.json();
}

// ── 재고 조회 ──────────────────────────────────────────────

export async function fetchAllInventory() {
    const r = await apiFetch("/api/inventory");
    return r.data;
}

export async function fetchEmployees() {
    const r = await apiFetch("/api/employees");
    return r.data;
}

export async function fetchPendingChanges() {
    const r = await apiFetch("/api/pending_changes");
    return r.data;
}

// ── inventory CRUD ─────────────────────────────────────────

export async function apiInsertItem(data) {
    return apiFetch("/api/inventory", {
        method: "POST",
        body: JSON.stringify({ data }),
    });
}

export async function apiUpdateItem(id, fields) {
    return apiFetch(`/api/inventory/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify({ data: fields }),
    });
}

export async function apiDeleteItem(id) {
    return apiFetch(`/api/inventory/${encodeURIComponent(id)}`, {
        method: "DELETE",
    });
}

// ── holding_records CRUD ───────────────────────────────────

export async function apiInsertHoldingRecord(holdId, data) {
    return apiFetch("/api/holding_records", {
        method: "POST",
        body: JSON.stringify({ id: holdId, data }),
    });
}

export async function apiUpdateHoldingRecord(id, fields) {
    return apiFetch(`/api/holding_records/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: JSON.stringify({ data: fields }),
    });
}

export async function apiDeleteHoldingRecord(id) {
    return apiFetch(`/api/holding_records/${encodeURIComponent(id)}`, {
        method: "DELETE",
    });
}

export async function apiGetHoldingCount(pk) {
    const r = await apiFetch(`/api/holding_records/count/${encodeURIComponent(pk)}`);
    return r.count;
}
