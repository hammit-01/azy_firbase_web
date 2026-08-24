// firebase.js — MySQL API 버전 (Firebase SDK 제거)
import { state } from "./state.js";
import { renderTable, renderWarehouseOptions, renderBrandOptions, renderProductNameOptions } from "./table.js";
import { renderSelectData } from "./panel.js";
import { fetchAllInventory, fetchEmployees, fetchMovingInventory, fetchYesterdayInventory } from "./api.js";

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
// moving_inventory 행 → 테이블에서 쓰는 형태로 변환. 출고창고 정보가 없으므로
// "창고" 컬럼 자리에는 이동창고(도착지)를 그대로 넣는다. _isMoving으로 표시해서
// table.js가 노란 배경을 입히고 체크박스를 비활성화(읽기 전용, CRUD 대상 아님)한다.
function normalizeMovingRow(r) {
    return {
        id: `moving:${r.id}`,
        _rawId: r.id,
        _isMoving: true,
        상품명: r.상품명,
        브랜드: r.브랜드,
        등급: r.등급,
        ESTNO: r.ESTNO,
        재고: r.재고,
        BL: r.BL,
        창고: r.이동창고,
        메모: r.비고,
        // DB 상태 컬럼은 한글 "이고" 그대로 저장되는데, 기존 상태뱃지 시스템은
        // 영문 코드 "moving"에 "이고" 라벨/주황 배지를 이미 매핑해뒀으므로
        // 그 기존 뱃지를 그대로 재사용하도록 코드로 변환
        상태: r.상태 === "이고" ? "moving" : r.상태,
    };
}

// 업데이트 탭 비교 기준(어제 마감 스냅샷) 로드 — 실패해도 오늘 데이터 표시엔 지장 없게 조용히 무시
async function loadYesterdaySnapshot() {
    try {
        const map = new Map();
        if (window.__AZY_API_MODE) {
            const rows = await fetchYesterdayInventory();
            rows.forEach(r => map.set(`azy:${r.id}`, r));
        } else {
            const [mainRows, azyRows] = await Promise.all([
                fetchYesterdayInventory(false),
                fetchYesterdayInventory(true),
            ]);
            mainRows.forEach(r => map.set(`main:${r.id}`, r));
            azyRows.forEach(r => map.set(`azy:${r.id}`, r));
        }
        state.yesterdayById = map;
    } catch (e) {
        console.warn("[API] yesterday_inventory 조회 실패:", e.message);
    }
}

export async function fetchAllData() {
    try {
        let movingRows = [];
        try {
            movingRows = (await fetchMovingInventory()).map(normalizeMovingRow);
        } catch (e) {
            console.warn("[API] moving_inventory 조회 실패:", e.message);
        }
        // 익일 이고 미리보기 노출은 로그인만 하면 됨(2026-08-24 전체 공개) —
        // login.js를 여기서 import하면 순환참조 위험이 있어 기존 패턴대로
        // localStorage 직접 확인.
        let previewEnabled = false;
        try {
            const u = JSON.parse(localStorage.getItem("azy_login_user") || "null");
            previewEnabled = !!u?.권한;
        } catch {}
        if (!previewEnabled) movingRows = movingRows.filter(r => r.메모 !== "익일 이고");

        loadYesterdaySnapshot(); // 렌더를 막지 않게 병행 — 도착하면 다음 렌더부터 반영됨

        if (window.__AZY_API_MODE) {
            const rows = await fetchAllInventory();
            state.allData = [
                ...rows.map(r => ({ ...r, _source: "azy", _rawId: r.id })),
                ...movingRows,
            ];
        } else {
            const [mainRows, azyRows] = await Promise.all([
                fetchAllInventory(false),
                fetchAllInventory(true),
            ]);

            // 일부 창고(예: 대청)는 통관분 계정과 일반 계정이 같은 재고를 그대로 보여줘서
            // 두 테이블에 동일 창고+BL이 통째로 중복 적재된다 — 화면에서는 통관분(main) 쪽을 우선하고
            // 같은 창고+BL이 이미 main에 있는 azy 행은 제외해 중복 표시/합계를 막는다.
            // (BL만으로 비교하면 같은 BL이 서로 다른 창고에 나뉘어 실린 정상 케이스까지 지워진다)
            const mainBLWarehouses = new Set(
                mainRows.filter(r => r.BL).map(r => `${r.BL}|${r.창고}`)
            );
            const azyDeduped = azyRows.filter(r => !r.BL || !mainBLWarehouses.has(`${r.BL}|${r.창고}`));

            state.allData = [
                ...mainRows.map(r => ({ ...r, _source: "main", _rawId: r.id })),
                ...azyDeduped.map(r => ({ ...r, _source: "azy", _rawId: r.id, id: `azy:${r.id}` })),
                ...movingRows,
            ];
        }
        renderTable();
        renderWarehouseOptions();
        renderBrandOptions();
        renderProductNameOptions();
        const panelOpen = !!document.querySelector(".holding-card, .update-card, .insert-card");
        if (!panelOpen) renderSelectData();
    } catch (e) {
        console.warn("[API] fetchAllData 오류:", e.message);
    }
}

// Firebase 호환용 더미 (crud_history.js 등에서 import할 수 있음)
export const db = null;
export async function handleQuotaExceeded() { return false; }
