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

function closePopover() {
    document.querySelector(".login-btn")?.classList.remove("active");
    document.querySelector(".login-popover")?.classList.remove("open");
}

// 편집자만 추가/수정/전체삭제 가능 — 사원 및 비로그인은 숨김 (화면 표시만, 서버단 권한 검사는 없음)
const EDITOR_ONLY_SELECTORS = [".insert-btn", ".update-btn", ".all-delete-btn"];
// 로그인만 하면 사원도 사용 가능 — 비로그인일 때만 숨김
const LOGIN_ONLY_SELECTORS = [".holding-btn", ".rollback-btn"];

function applyRoleVisibility(role) {
    const hideEditorOnly = role !== "편집자";
    EDITOR_ONLY_SELECTORS.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.style.display = hideEditorOnly ? "none" : "";
    });

    const hideLoginOnly = !role;
    LOGIN_ONLY_SELECTORS.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.style.display = hideLoginOnly ? "none" : "";
    });
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
        renderLoggedOut();
        applyRoleVisibility(undefined);
        cancelActiveForm();
        closePopover();
    });
}
