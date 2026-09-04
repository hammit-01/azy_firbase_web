import { state } from "./state.js";
import { dom } from "./dom.js";

export function employeeSelect(cls, dataId = "", currentVal = "") {
    const opts = state.employees
        .map(e => `<option value="${e["이름"]}" ${e["이름"] === currentVal ? "selected" : ""}>${e["이름"]}</option>`)
        .join("");
    const id = dataId ? `data-id="${dataId}"` : "";
    return `<select class="${cls} input-box" ${id}>
                <option value="">담당자 선택</option>
                ${opts}
            </select>`;
}

// 창고이동 탭(2026-09-04) — 담당자를 타이핑하면 맞는 이름이 뜨고 아래 방향키로
// 골라 선택할 수 있게(사용자 요청) 순정 select 대신 datalist 붙은 입력창으로.
// datalist id는 카드마다(같은 화면에 여러 장 뜰 수 있어) dataId 기준으로 유일하게.
export function employeeAutocomplete(cls, dataId = "", currentVal = "") {
    const listId = `employee-datalist-${dataId || Math.random().toString(36).slice(2)}`;
    const opts = state.employees.map(e => `<option value="${e["이름"]}">`).join("");
    const id = dataId ? `data-id="${dataId}"` : "";
    return `<input type="text" list="${listId}" class="${cls} input-box" ${id} value="${currentVal}" placeholder="담당자 입력" autocomplete="off">
            <datalist id="${listId}">${opts}</datalist>`;
}

// show-state 필터와 동일한 어휘 — 추가/수정 폼에서 상태를 직접 고를 때도 같은 옵션을 씀
const STATE_OPTIONS = [
    ["없음", "없음"],
    ["holding", "예약"],
    ["freeze", "동결"],
    ["stopped", "사용불가"],
    ["moving", "이고"],
    ["특이품", "특이품"],
    ["null", "null(정보누락)"],
];

export function stateSelect(cls, currentVal = "없음", dataId = "") {
    const opts = STATE_OPTIONS
        .map(([value, label]) => `<option value="${value}" ${value === currentVal ? "selected" : ""}>${label}</option>`)
        .join("");
    const id = dataId ? `data-id="${dataId}"` : "";
    return `<select class="${cls} cell-input" ${id}>${opts}</select>`;
}

// 창고이동 탭(2026-09-04, 관리자+8001 테스트 기능) — 배차자/이동창고 둘 다 회사에서
// 실제 쓰는 고정 목록이라(state.employees처럼 서버 목록이 아님) 그냥 하드코딩.
const MOVE_DISPATCHER_OPTIONS = ["새벽", "고열의", "임기사님", "진기사님", "유기사님", "타업체", "차두만", "택기사님", "김태욱"];
const MOVE_WAREHOUSE_OPTIONS = ["곤지암", "직배", "수탁", "마장", "배민", "미트박스"];

export function dispatcherSelect(cls, dataId = "", currentVal = "") {
    const opts = MOVE_DISPATCHER_OPTIONS.map(name => `<option value="${name}" ${name === currentVal ? "selected" : ""}>${name}</option>`).join("");
    const id = dataId ? `data-id="${dataId}"` : "";
    return `<select class="${cls} input-box" ${id}>
                <option value="">배차자 선택</option>
                ${opts}
            </select>`;
}

export function moveWarehouseSelect(cls, dataId = "", currentVal = "") {
    const opts = MOVE_WAREHOUSE_OPTIONS.map(name => `<option value="${name}" ${name === currentVal ? "selected" : ""}>${name}</option>`).join("");
    const id = dataId ? `data-id="${dataId}"` : "";
    return `<select class="${cls} input-box" ${id}>
                <option value="">이동창고 선택</option>
                ${opts}
            </select>`;
}

// 사이트 이름 옆에 "총 N행, M박스 선택" 표시 — 체크된 행이 바뀔 때마다 호출됨
export function renderSelectData() {
    const summary = document.querySelector(".selection-summary");
    if (!summary) return;

    if (state.selectedItems.size === 0) {
        summary.textContent = "";
        summary.classList.remove("visible");
        return;
    }

    let qty = 0;
    state.selectedItems.forEach(item => { qty += Number(item.qty) || 0; });

    summary.textContent = `총 ${state.selectedItems.size}행,\n${qty}박스 선택`;
    summary.classList.add("visible");
}

// 상품 추가 — 오른쪽 패널 대신 테이블 맨 위에 입력 가능한 행을 하나 띄운다.
export function renderInsert() {
    if (!dom.insertRowsBody) return;
    if (dom.insertRowsBody.children.length > 0) return;
    dom.insertRowsBody.insertAdjacentHTML("beforeend", createInsertRow());
}

export function createInsertRow() {
    return `
        <tr class="insert-card">
            <td><button class="add-insert-row-btn" title="입력행 추가">+</button></td>
            <td data-label="상품명"><input type="text" class="insert-name cell-input" placeholder="상품명"></td>
            <td data-label="브랜드"><input type="text" class="insert-brand cell-input" placeholder="브랜드"></td>
            <td data-label="등급"><input type="text" class="insert-grade cell-input" placeholder="등급"></td>
            <td data-label="ESTNO"><input type="text" class="insert-estNo cell-input" placeholder="ESTNO"></td>
            <td data-label="재고"><input type="number" class="insert-qty cell-input" placeholder="재고"></td>
            <td data-label="BL"><input type="text" class="insert-bl cell-input" placeholder="BL"></td>
            <td data-label="창고"><input type="text" class="insert-warehouse cell-input" placeholder="창고"></td>
            <td data-label="예약"></td>
            <td data-label="가용"></td>
            <td data-label="유통기한"><input type="date" class="insert-dueDate cell-input"></td>
            <td data-label="평중"><input type="number" step="0.01" class="insert-weight cell-input" placeholder="평중"></td>
            <td data-label="비고">
                <div class="insert-row-memo-cell">
                    <input type="text" class="input-note insert-memo cell-input" placeholder="비고">
                    ${stateSelect("insert-state")}
                    <button class="select-insert-btn" title="저장">✓</button>
                    <button class="remove-insert-btn card-close-btn" title="취소">✕</button>
                </div>
                <input type="hidden" class="insert-releaseDate" value="">
                <input type="hidden" class="insert-holding" value="">
            </td>
        </tr>
    `;
}
