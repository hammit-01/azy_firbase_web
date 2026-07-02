import { initializeApp }
from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";

import {
    getFirestore,
    collection,
    getDocs,
    onSnapshot,
    doc,
    getDoc,
    setDoc
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { showToast } from "./ui.js";

// ★ Primary: 현재 운영 프로젝트 (변경 금지)
const PRIMARY_CONFIG = {
    apiKey: "AIzaSyBMzVr396MMhlAEwsOfMhVLrOMnRMfWkgQ",
    authDomain: "azy7503-d80d9.firebaseapp.com",
    projectId: "azy7503-d80d9"
};

// ★ Secondary: Firebase 콘솔에서 새 프로젝트 생성 후 아래 값을 교체하세요
//   https://console.firebase.google.com → 프로젝트 설정 → 앱 추가 → 웹
const SECONDARY_CONFIG = {
    apiKey: "AIzaSyDCdjxL5U0vmEkGQEroPo4-zOP33nrKSBQ",
    authDomain: "awhw-0001.firebaseapp.com",
    projectId: "awhw-0001",
};

// Secondary 설정이 완료됐는지 확인 (placeholder 그대로면 비활성)
const SECONDARY_READY = SECONDARY_CONFIG.projectId !== "SECONDARY_PROJECT_ID";

export let db;
let _primaryDb;
let _secondaryDb;
let _activeDbName = "primary";

const _renderHooks = [];
export function addRenderHook(fn) { _renderHooks.push(fn); }


export async function initFirebase() {
    const primaryApp = initializeApp(PRIMARY_CONFIG, "primary");
    _primaryDb = getFirestore(primaryApp);

    if (SECONDARY_READY) {
        const secondaryApp = initializeApp(SECONDARY_CONFIG, "secondary");
        _secondaryDb = getFirestore(secondaryApp);

        // Secondary의 _meta/active_db 마커로 활성 DB 결정
        try {
            const markerSnap = await getDoc(doc(_secondaryDb, "_meta", "active_db"));
            if (markerSnap.exists() && markerSnap.data().active === "secondary") {
                _activeDbName = "secondary";
            }
        } catch (e) {
            console.warn("[Firebase] Secondary 마커 확인 실패, Primary 사용:", e.message);
        }

        // 마커 실시간 감시 → 백엔드가 DB 전환 시 페이지 자동 리로드
        onSnapshot(
            doc(_secondaryDb, "_meta", "active_db"),
            (snap) => {
                const newActive = snap.exists() ? (snap.data().active || "primary") : "primary";
                if (newActive !== _activeDbName) {
                    console.warn(`[Firebase] DB 전환 감지: ${_activeDbName} → ${newActive}, 리로드`);
                    setTimeout(() => window.location.reload(), 800);
                }
            },
            (err) => console.warn("[Firebase] Secondary 마커 감시 오류:", err.message)
        );
    }

    db = (_activeDbName === "secondary" && _secondaryDb) ? _secondaryDb : _primaryDb;
    console.log(`[Firebase] 활성 DB: ${_activeDbName.toUpperCase()}${SECONDARY_READY ? "" : " (Secondary 미설정)"}`);
    return db;
}

// 할당량 초과 시 반대 DB로 자동 전환
export async function handleQuotaExceeded(err) {
    if (err?.code !== "resource-exhausted") return false;

    const target = _activeDbName === "primary" ? "secondary" : "primary";
    console.warn(`[Firebase] ${_activeDbName.toUpperCase()} 할당량 초과 → ${target.toUpperCase()} 전환 시도`);

    if (!SECONDARY_READY || !_secondaryDb) {
        showToast("⚠ DB 할당량 초과. Secondary DB 미설정.", "error");
        return true;
    }

    try {
        await setDoc(doc(_secondaryDb, "_meta", "active_db"), { active: target });
        showToast(`⚠ 할당량 초과 — ${target === "secondary" ? "예비" : "주"} DB로 전환 중...`, "info");
        setTimeout(() => window.location.reload(), 1200);
    } catch (e2) {
        console.error("[Firebase] DB 전환 실패:", e2.message);
        showToast("⚠ DB 할당량 초과. 페이지를 새로고침합니다.", "error");
        setTimeout(() => window.location.reload(), 3000);
    }
    return true;
}


export async function loadEmployees() {
    const snap = await getDocs(collection(db, "employees"));
    state.employees = snap.docs
        .map(d => d.data())
        .sort((a, b) => a["이름"].localeCompare(b["이름"], "ko"));
}

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5분

export async function subscribeData() {
    await fetchAllData();
    setInterval(fetchAllData, POLL_INTERVAL_MS);
    _subscribePendingChanges();
}

function _subscribePendingChanges() {
    onSnapshot(collection(db, "pending_changes"), (snap) => {
        state.pendingChanges = snap.docs.map(d => ({ id: d.id, ...d.data() }));
        _renderHooks.forEach(fn => { try { fn(); } catch(e) {} });
    }, (err) => {
        console.warn("[Firebase] pending_changes 구독 오류:", err.message);
    });
}

export async function fetchAllData() {
    try {
        const snap = await getDocs(collection(db, "all_data"));
        state.allData = snap.docs.map(d => ({ id: d.id, ...d.data() }));
        renderTable();
        const panelOpen = !!document.querySelector(".holding-card, .update-card, .insert-card");
        if (!panelOpen) renderSelectData();
        _renderHooks.forEach(fn => { try { fn(); } catch(e) {} });
    } catch (e) {
        const handled = await handleQuotaExceeded(e);
        if (!handled) console.warn("[Firebase] fetchAllData 오류:", e.message);
    }
}
