import { state } from "./state.js";
import { dom } from "./dom.js";

function whClass(warehouse) {
    const map = {
        "곤지암": "wh-곤지암",
        "곤CS":   "wh-곤CS",
        "곤SWC":  "wh-곤SWC",
        "곤대재":  "wh-곤대재",
        "곤대청":  "wh-곤대청",
        "곤삼진2": "wh-곤삼진2",
        "곤에이스처인": "wh-곤에이스처인",
    };
    return map[warehouse] ?? "wh-default";
}

export function clearPanels(id) {
    const insert = document.querySelector(`.insert-panel[data-id="${id}"]`);
    const update = document.querySelector(`.update-panel[data-id="${id}"]`);
    const holding = document.querySelector(`.holding-panel[data-id="${id}"]`);

    if (insert) insert.innerHTML = "";
    if (update) update.innerHTML = "";
    if (holding) holding.innerHTML = "";
}

export function renderSelectData() {
    const { sideBox, container } = dom;

    if (!sideBox || !container) return;

    if (state.selectedItems.size === 0) {
        container.classList.remove("active");
        sideBox.innerHTML = "";
        return;
    }

    container.classList.add("active");

    let gridHtml = "";
    let panelsHtml = "";

    state.selectedItems.forEach((item, id) => {
        gridHtml += `
            <div class="selected-item">
                <div class="selected-header">
                    <div class="selected-info">
                        <div class="selected-title">${item.brand} ${item.name}</div>
                        <div class="selected-meta">
                            ${item.grade     ? `<span class="s-tag">${item.grade}</span>` : ""}
                            ${item.estNo     ? `<span class="s-tag">${item.estNo}</span>` : ""}
                            ${item.qty       ? `<span class="s-tag s-tag-qty">${item.qty}박스</span>` : ""}
                            ${item.warehouse ? `<span class="s-tag ${whClass(item.warehouse)}">${item.warehouse}</span>` : ""}
                        </div>
                    </div>
                    <button class="cancel-btn" data-id="${id}">✕</button>
                </div>
            </div>
        `;
        panelsHtml += `
            <div class="insert-panel" data-id="${id}"></div>
            <div class="update-panel" data-id="${id}"></div>
            <div class="holding-panel" data-id="${id}"></div>
        `;
    });

    sideBox.innerHTML = `
        <div class="selected-grid">${gridHtml}</div>
        <div class="panels-area">${panelsHtml}</div>
    `;
}

export function renderInsert() {
    const { sideBox, container } = dom;
    if (!sideBox) return;

    container?.classList.add("active");

    sideBox.innerHTML = `
        <div class="insert-header-wrap">
            <span class="insert-header-title">항목 추가</span>
            <button class="insertRow-btn">+ 행 추가</button>
        </div>
        <div class="insert-list"></div>
    `;

    document.querySelector(".insert-list")
        .insertAdjacentHTML("beforeend", createInsertRow());
}

export function createInsertRow() {
    return `
        <div class="insert-card">
            <div class="card-top-bar">
                <button class="remove-insert-btn card-close-btn">✕</button>
            </div>
            <div class="insert-grid">
                <div class="form-field">
                    <label class="form-label">상품명 *</label>
                    <input type="text" class="insert-name input-box input-required" placeholder="상품명">
                </div>
                <div class="form-field">
                    <label class="form-label">브랜드 *</label>
                    <input type="text" class="insert-brand input-box input-required" placeholder="브랜드">
                </div>
                <div class="form-field">
                    <label class="form-label">등급 *</label>
                    <input type="text" class="insert-grade input-box input-required" placeholder="등급">
                </div>
                <div class="form-field">
                    <label class="form-label">ESTNO *</label>
                    <input type="text" class="insert-estNo input-box input-required" placeholder="ESTNO">
                </div>
                <div class="form-field">
                    <label class="form-label">재고 *</label>
                    <input type="number" class="insert-qty input-box input-required" placeholder="재고">
                </div>
                <div class="form-field">
                    <label class="form-label">BL *</label>
                    <input type="text" class="insert-bl input-box input-required" placeholder="BL번호">
                </div>
                <div class="form-field">
                    <label class="form-label">창고 *</label>
                    <input type="text" class="insert-warehouse input-box input-required" placeholder="창고">
                </div>
                <div class="form-field">
                    <label class="form-label">유통기한 *</label>
                    <input type="date" class="insert-dueDate input-box input-required">
                </div>
                <div class="form-field">
                    <label class="form-label">평중 *</label>
                    <input type="number" class="insert-weight input-box input-required" placeholder="평중">
                </div>
                <div class="form-field">
                    <label class="form-label">출고일</label>
                    <input type="date" class="insert-releaseDate input-box">
                </div>
                <div class="form-field">
                    <label class="form-label">홀딩</label>
                    <input type="text" class="insert-holding input-box" placeholder="홀딩">
                </div>
                <div class="form-field">
                    <label class="form-label">상태</label>
                    <select class="insert-state input-box">
                        <option value="non">없음</option>
                        <option value="freeze">동결</option>
                        <option value="stopped">사용불가</option>
                        <option value="moving">이고</option>
                    </select>
                </div>
            </div>
            <div class="insert-footer">
                <input type="text" class="input-note insert-memo" placeholder="메모">
                <button class="select-insert-btn insert-submit-btn">추가</button>
            </div>
        </div>
    `;
}

export function renderUpdate() {
    state.selectedItems.forEach((item, id) => clearPanels(id));

    const grid = document.querySelector(".selected-grid");
    if (grid) grid.style.display = "none";

    const panelsArea = document.querySelector(".panels-area");
    if (panelsArea) panelsArea.classList.add("panels-grid");

    state.selectedItems.forEach((item, id) => {
        const target = document.querySelector(`.update-panel[data-id="${id}"]`);
        if (!target) return;

        const dataState = item.dataState || "";

        target.innerHTML = `
            <div class="update-card">
                <div class="panel-item-title">
                    <span>${item.brand} ${item.name}</span>
                    <span class="s-tag s-tag-qty">${item.qty}박스</span>
                    <span class="s-tag ${whClass(item.warehouse)}">${item.warehouse}</span>
                    <button class="cancel-btn" data-id="${id}" style="margin-left:auto;">✕</button>
                </div>
                <div class="update-pan insert-grid" data-id="${id}">
                    <div class="form-field">
                        <label class="form-label">상품명 *</label>
                        <input type="text" value="${item.name}" class="update-name input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">브랜드 *</label>
                        <input type="text" value="${item.brand}" class="update-brand input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">등급 *</label>
                        <input type="text" value="${item.grade}" class="update-grade input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">ESTNO *</label>
                        <input type="text" value="${item.estNo}" class="update-estNo input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">재고 *</label>
                        <input type="number" value="${item.qty}" class="update-qty input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">BL *</label>
                        <input type="text" value="${item.bl}" class="update-bl input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">창고 *</label>
                        <input type="text" value="${item.warehouse}" class="update-warehouse input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">유통기한 *</label>
                        <input type="date" value="${item.dueDate}" class="update-dueDate input-box input-required" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">평중 *</label>
                        <input type="number" value="${item.weight}" class="update-weight input-box input-required" data-id="${id}">
                    </div>
                    ${dataState === "holding" ? `
                    <div class="form-field">
                        <label class="form-label">출고일</label>
                        <input type="date" value="${item.releaseDate}" class="update-releaseDate input-box" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">홀딩</label>
                        <input type="text" value="${item.holding}" class="update-holding input-box" data-id="${id}">
                    </div>` : `
                    <input type="hidden" class="update-releaseDate" data-id="${id}" value="${item.releaseDate}">
                    <input type="hidden" class="update-holding"     data-id="${id}" value="${item.holding}">`}
                    <div class="form-field">
                        <label class="form-label">상태</label>
                        <select class="update-state input-box" data-id="${id}">
                            <option value="non"     ${dataState === "non" || dataState === "없음" || dataState === "" ? "selected" : ""}>없음</option>
                            <option value="holding" ${dataState === "holding" ? "selected" : ""}>홀딩</option>
                            <option value="freeze"  ${dataState === "freeze"  ? "selected" : ""}>동결</option>
                            <option value="stopped" ${dataState === "stopped" ? "selected" : ""}>사용불가</option>
                            <option value="moving"  ${dataState === "moving"  ? "selected" : ""}>이고</option>
                        </select>
                    </div>
                </div>
                <div class="update-footer">
                    <input type="text" class="input-note insert-memo" data-id="${id}" placeholder="메모" value="${item.memo || ""}">
                    <div class="update-actions">
                        <button class="select-update-btn update-confirm-btn" data-id="${id}">수정</button>
                        <button class="select-delete-btn update-delete-btn" data-id="${id}">삭제</button>
                    </div>
                </div>
            </div>
        `;
    });
}

export function renderHolding() {
    state.selectedItems.forEach((item, id) => clearPanels(id));

    const grid = document.querySelector(".selected-grid");
    if (grid) grid.style.display = "none";

    const panelsArea = document.querySelector(".panels-area");
    if (panelsArea) panelsArea.classList.add("panels-grid");

    state.selectedItems.forEach((item, id) => {
        const target = document.querySelector(`.holding-panel[data-id="${id}"]`);
        if (!target) return;

        target.innerHTML = `
            <div class="holding-card">
                <div class="panel-item-title">
                    <span>${item.brand} ${item.name}</span>
                    <span class="s-tag s-tag-qty">${item.qty}박스</span>
                    <span class="s-tag ${whClass(item.warehouse)}">${item.warehouse}</span>
                    <button class="cancel-btn" data-id="${id}" style="margin-left:auto;">✕</button>
                </div>
                <div class="holding-pan insert-grid" data-id="${id}">
                    <div class="form-field">
                        <label class="form-label">홀딩 개수</label>
                        <input type="number" class="hold-qty input-box" data-id="${id}" placeholder="개수">
                    </div>
                    <div class="form-field">
                        <label class="form-label">출고 일자</label>
                        <input type="date" class="hold-releaseDate input-box" data-id="${id}">
                    </div>
                    <div class="form-field">
                        <label class="form-label">홀딩자</label>
                        <input type="text" class="hold-note input-box" data-id="${id}" placeholder="홀딩자">
                    </div>
                </div>
                <div class="update-footer">
                    <input type="text" class="input-note insert-memo" data-id="${id}" placeholder="메모" value="${item.memo || ""}">
                    <button class="select-holding-btn holding-confirm-btn" data-id="${id}">홀딩</button>
                </div>
            </div>
        `;
    });
}

export function renderFooter(type) {
    const { sideBox } = dom;
    sideBox.querySelectorAll(".footer").forEach(el => el.remove());

    let totalQty = 0;
    let totalWeight = 0;

    state.selectedItems.forEach(item => {
        totalQty += Number(item.qty) || 0;
        totalWeight += Number(item.weight) || 0;
    });

    let html = "";

    if (type === "update") {
        html = `
            <div class="footer">
                <div>총 ${totalQty} 박스</div>
                <div>총 ${totalWeight}kg</div>
                <button class="all-update-btn">전체 수정</button>
            </div>
        `;
    } else if (type === "holding") {
        html = `
            <div class="footer">
                <div>총 ${totalQty} 박스</div>
                <button class="all-holding-btn">전체 홀딩</button>
            </div>
        `;
    } else if (type === "insert") {
        html = `
            <div class="footer">
                <button class="all-insert-btn">전체 추가</button>
            </div>
        `;
    }

    sideBox.insertAdjacentHTML("beforeend", html);
}
