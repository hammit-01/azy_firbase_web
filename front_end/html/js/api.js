// api.js — MySQL 백엔드 API 클라이언트
const API_BASE = window.location.origin;

// azy가 명시되면 그 값을 쓰고, 아니면 페이지 전역 플래그(__AZY_API_MODE)를 따른다.
// 통관분 페이지에서 타창고 데이터를 함께 불러올 때 호출별로 azy=true를 넘겨 라우팅한다.
function _resolvePath(p, azy) {
    const useAzy = azy ?? window.__AZY_API_MODE;
    if (!useAzy) return p;
    return p
        .replace(/^\/api\/inventory/, "/api/azy_inventory")
        .replace(/^\/api\/holding_records/, "/api/azy_holding_records");
}

export async function apiFetch(path, options = {}, azy) {
    const res = await fetch(`${API_BASE}${_resolvePath(path, azy)}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) throw new Error(`API ${path} 실패: ${res.status}`);
    return res.json();
}

// ── 재고 조회 ──────────────────────────────────────────────

export async function fetchAllInventory(azy) {
    const r = await apiFetch("/api/inventory", {}, azy);
    return r.data;
}

export async function fetchEmployees() {
    const r = await apiFetch("/api/employees");
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

export async function apiInsertHoldingRecord(holdId, data, azy) {
    return apiFetch("/api/holding_records", {
        method: "POST",
        body: JSON.stringify({ id: holdId, data }),
    }, azy);
}

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

export async function apiGetHoldingCount(pk, azy) {
    const r = await apiFetch(`/api/holding_records/count/${encodeURIComponent(pk)}`, {}, azy);
    return r.count;
}
