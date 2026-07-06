// firebase.js — MySQL API 버전 (Firebase SDK 제거)
import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { fetchAllInventory, fetchEmployees, fetchPendingChanges } from "./api.js";

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5분

export async function initFirebase() {
    // MySQL 버전: 별도 초기화 불필요
    return true;
}

export async function loadEmployees() {
    const rows = await fetchEmployees();
    state.employees = rows.sort((a, b) => a["이름"].localeCompare(b["이름"], "ko"));
}

export async function subscribeData() {
    await fetchAllData();
    setInterval(fetchAllData, POLL_INTERVAL_MS);
    _pollPendingChanges();
}

function _pollPendingChanges() {
    const poll = async () => {
        try {
            const rows = await fetchPendingChanges();
            state.pendingChanges = rows;
        } catch (e) {
            console.warn("[API] pending_changes 조회 오류:", e.message);
        }
    };
    poll();
    setInterval(poll, POLL_INTERVAL_MS);
}

export async function fetchAllData() {
    try {
        const rows = await fetchAllInventory();
        state.allData = rows;
        renderTable();
        const panelOpen = !!document.querySelector(".holding-card, .update-card, .insert-card");
        if (!panelOpen) renderSelectData();
    } catch (e) {
        console.warn("[API] fetchAllData 오류:", e.message);
    }
}

// Firebase 호환용 더미 (crud_history.js 등에서 import할 수 있음)
export const db = null;
export function addRenderHook(fn) {}
export async function handleQuotaExceeded() { return false; }
