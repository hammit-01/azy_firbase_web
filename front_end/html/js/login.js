import { apiLogin } from "./api.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { state } from "./state.js";
import { dom } from "./dom.js";

const STORAGE_KEY = "azy_login_user";

export function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch {
        return null;
    }
}

// 관리자는 편집자와 동일하게 모든 기능에 접근 가능(2026-08-13)
export function hasEditorAccess(role) {
    return role === "편집자" || role === "관리자";
}

// 전략단가 탭 추가/수정/삭제는 편집자도 아니고 관리자만(2026-08-20, 우선 관리자만
// 열어두고 필요하면 나중에 편집자로 넓히기로 함).
export function hasPriceEditAccess(role) {
    return role === "관리자";
}

// 신규 기능 단계적 롤아웃 게이트(2026-08-24) — 관리자 권한 + 로컬 테스트
// 서버(8001)에서만 켠다. prod(8000)나 일반 권한에서는 기존 동작 그대로.
export function hasAdminAccess(role) {
    return role === "관리자";
}
export function isAdminTestFeatureEnabled() {
    return hasAdminAccess(getStoredUser()?.권한) && window.location.port === "8001";
}

function closePopover() {
    document.querySelector(".login-btn")?.classList.remove("active");
    document.querySelector(".login-popover")?.classList.remove("open");
}

// 편집자만 업데이트(어제 대비 변경) 가능 — 사원 및 비로그인은 숨김
// (화면 표시만, 서버단 권한 검사는 없음). 추가/수정/예약/전체취소/전체삭제는
// 탭에 따라서도 달라져서(2026-08-19, events.js의 applyTabButtonVisibility와
// 동일 규칙) 아래에서 따로 처리 — 로그인/로그아웃 시에도 그 규칙이 깨지지 않게.
const EDITOR_ONLY_SELECTORS = [".changes-tab-btn"];
// 로그인만 하면 사원도 사용 가능 — 비로그인일 때만 숨김. 되돌리기는 탭 제한도
// 같이 받아서(업데이트 탭에서 숨김, 2026-08-20) 아래에서 따로 처리.
const LOGIN_ONLY_SELECTORS = [".reservations-tab-btn", ".order-sheet-tab-btn"];

// 현재 열려 있는 탭 이름 — events.js를 import하지 않고 DOM만으로 판단
// (순환 참조 방지). .table-container가 안 보이면 그 컨테이너가 곧 현재 탭.
function _currentTabName() {
    if (document.querySelector(".reservations-container")?.style.display === "") return "reservations";
    if (document.querySelector(".sales-container")?.style.display === "") return "sales";
    if (document.querySelector(".price-container")?.style.display === "") return "price";
    if (document.querySelector(".order-sheet-container")?.style.display === "") return "order-sheet";
    if (document.querySelector(".changes-container")?.style.display === "") return "changes";
    return "main";
}

export function applyRoleVisibility(role) {
    const hideEditorOnly = !hasEditorAccess(role);
    EDITOR_ONLY_SELECTORS.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.style.display = hideEditorOnly ? "none" : "";
    });

    const hideLoginOnly = !role;
    LOGIN_ONLY_SELECTORS.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.style.display = hideLoginOnly ? "none" : "";
    });

    // 추가/수정/예약 — 탭 제한 + 권한 제한을 같이 적용(2026-08-19)
    const tab = _currentTabName();
    const isEditor = hasEditorAccess(role);
    const mainOnly = tab === "main";
    const insertBtn = document.querySelector(".insert-btn");
    const updateBtn = document.querySelector(".update-btn");
    const holdingBtn = document.querySelector(".holding-btn");
    const clearBtn = document.querySelector(".clear-btn");
    const allDeleteBtn = document.querySelector(".all-delete-btn");
    const rollbackBtn = document.querySelector(".rollback-btn");
    // 전략단가 탭의 "추가"는 관리자만(2026-08-20) — 다른 탭은 기존처럼 편집자도 가능.
    const canAddOnTab = tab === "price" ? hasPriceEditAccess(role) : isEditor;
    if (insertBtn) insertBtn.style.display = (tab !== "reservations" && tab !== "changes" && canAddOnTab) ? "" : "none";
    if (updateBtn) updateBtn.style.display = (mainOnly && isEditor) ? "" : "none";
    if (holdingBtn) holdingBtn.style.display = (mainOnly && !!role) ? "" : "none";
    // 전체취소/전체삭제 — 타창고매출현황/전략단가/예약현황(나의예약)/업데이트에서는
    // 숨김, 재고장 탭에서만 노출(2026-08-20). 전체삭제는 기존처럼 편집자만.
    if (clearBtn) clearBtn.style.display = mainOnly ? "" : "none";
    if (allDeleteBtn) allDeleteBtn.style.display = (mainOnly && isEditor) ? "" : "none";
    // 되돌리기 — 업데이트 탭에서는 숨김(2026-08-20, 되돌릴 CRUD 자체가 없는 탭).
    if (rollbackBtn) rollbackBtn.style.display = (!!role && tab !== "changes") ? "" : "none";

    // 재고장 검색/필터(상품명·브랜드·창고·상태 + 검색1·검색2) — 전략단가/예약현황/
    // 타창고매출현황 탭은 각자 자체 검색/필터를 따로 쓰므로 이 재고장용 툴바는
    // 숨긴다(2026-08-19 전략단가, 2026-08-20 예약현황·타창고매출현황으로 확장).
    const toolbarRight = document.querySelector(".toolbar-right");
    if (toolbarRight) toolbarRight.style.display = mainOnly ? "" : "none";

    // 예약 현황 탭 라벨 — 편집자는 전체를 담당자별로 보고, 사원은 본인 예약만 보므로
    // 버튼 이름도 그에 맞게(2026-08-06)
    const reservationsBtn = document.querySelector(".reservations-tab-btn");
    if (reservationsBtn) {
        reservationsBtn.textContent = hasEditorAccess(role) ? "예약 현황" : "나의 예약";
    }
}

function renderLoggedIn(user) {
    document.querySelector(".login-btn-text").textContent = user.이름;
    document.querySelector(".login-form").style.display = "none";
    document.querySelector(".login-profile").style.display = "flex";
    document.querySelector(".login-profile-name").textContent = `${user.이름}님`;
    document.querySelector(".login-profile-role").textContent = user.권한 || "";
}

// 추가/수정/홀딩 중이던 행은 담당자 자동입력 등 로그인 상태에 따라 내용이 달라지므로,
// 로그인/로그아웃 시엔 렌더 캐시로 값 보존하지 말고 "전체 취소"와 동일하게 아예 닫아버린다
function cancelActiveForm() {
    state.selectedItems.clear();
    state.crudData = null;
    dom.container?.classList.remove("active");
    if (dom.sideBox) dom.sideBox.innerHTML = "";
    renderTable();
    renderSelectData();
}

function renderLoggedOut() {
    document.querySelector(".login-btn-text").textContent = "로그인";
    document.querySelector(".login-form").style.display = "";
    document.querySelector(".login-profile").style.display = "none";
}

export function initLogin() {
    const stored = getStoredUser();
    if (stored) renderLoggedIn(stored);
    applyRoleVisibility(stored?.권한);

    document.querySelector(".login-btn")?.addEventListener("click", (e) => {
        e.stopPropagation();
        document.querySelector(".login-btn")?.classList.toggle("active");
        document.querySelector(".login-popover")?.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
        if (e.target.closest(".toolbar-login")) return;
        closePopover();
    });

    const idInput  = document.getElementById("loginIdInput");
    const pwInput  = document.getElementById("loginPwInput");
    const errorEl  = document.querySelector(".login-error");

    async function submitLogin() {
        const id = idInput.value.trim();
        const pw = pwInput.value.trim();
        errorEl.textContent = "";

        if (!id || !pw) {
            errorEl.textContent = "아이디와 비밀번호를 입력해주세요.";
            return;
        }

        const user = await apiLogin(id, pw);
        if (!user) {
            errorEl.textContent = "아이디 또는 비밀번호가 올바르지 않습니다.";
            return;
        }

        localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
        idInput.value = "";
        pwInput.value = "";
        renderLoggedIn(user);
        applyRoleVisibility(user.권한);
        cancelActiveForm();
        closePopover();
    }

    document.querySelector(".login-submit-btn")?.addEventListener("click", submitLogin);
    pwInput?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") submitLogin();
    });

    document.querySelector(".logout-btn")?.addEventListener("click", () => {
        localStorage.removeItem(STORAGE_KEY);
        location.reload();
    });
}
