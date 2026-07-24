// firebase.js — MySQL API 버전 (Firebase SDK 제거)
import { state } from "./state.js";
import { renderTable, renderWarehouseOptions } from "./table.js";
import { renderSelectData } from "./panel.js";
import { fetchAllInventory, fetchEmployees } from "./api.js";

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
}

// 통관분 페이지(__AZY_API_MODE 없음)에서는 통관분(inventory) + 타창고(azy_inventory)를
// 동시에 불러와 화면에서만 하나로 합친다 — MySQL 테이블 자체는 그대로 분리 유지.
// 타창고 페이지(__AZY_API_MODE=true)는 기존처럼 azy_inventory만 그대로 보여준다.
// id는 두 테이블 간 충돌을 막기 위해 타창고 쪽만 "azy:" 접두사를 붙이고,
// 실제 백엔드 라우팅/쓰기에 쓸 원본 id는 _rawId, 출처는 _source로 각 행에 표시해둔다.
export async function fetchAllData() {
    try {
        if (window.__AZY_API_MODE) {
            const rows = await fetchAllInventory();
            state.allData = rows.map(r => ({ ...r, _source: "azy", _rawId: r.id }));
        } else {
            const [mainRows, azyRows] = await Promise.all([
                fetchAllInventory(false),
                fetchAllInventory(true),
            ]);

            // 일부 창고(예: 대청)는 통관분 계정과 일반 계정이 같은 재고를 그대로 보여줘서
            // 두 테이블에 동일 BL이 통째로 중복 적재된다 — 화면에서는 통관분(main) 쪽을 우선하고
            // 같은 BL이 이미 main에 있는 azy 행은 제외해 중복 표시/합계를 막는다.
            const mainBLs = new Set(mainRows.map(r => r.BL).filter(Boolean));
            const azyDeduped = azyRows.filter(r => !r.BL || !mainBLs.has(r.BL));

            state.allData = [
                ...mainRows.map(r => ({ ...r, _source: "main", _rawId: r.id })),
                ...azyDeduped.map(r => ({ ...r, _source: "azy", _rawId: r.id, id: `azy:${r.id}` })),
            ];
        }
        renderTable();
        renderWarehouseOptions();
        const panelOpen = !!document.querySelector(".holding-card, .update-card, .insert-card");
        if (!panelOpen) renderSelectData();
    } catch (e) {
        console.warn("[API] fetchAllData 오류:", e.message);
    }
}

// Firebase 호환용 더미 (crud_history.js 등에서 import할 수 있음)
export const db = null;
export async function handleQuotaExceeded() { return false; }
