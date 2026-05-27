import { state } from "./state.js";
import { dom } from "./dom.js";

const { selectedItems } = state;
let totalQty = 0;
let totalWeight = 0;
let total = 0;

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

    if (selectedItems.size === 0) {
        container.classList.remove("active");
        sideBox.innerHTML = "";
        return;
    }

    container.classList.add("active");

    let html = '';

    selectedItems.forEach((item, id) => {
        html += `
            <div class="selected-item">
                <div class="item-datas">
                    <button class="cancel-btn" data-id="${id}">X</button>
                    <div class = "item-data">
                        <b>${item.brand} ${item.name} ${item.grade} ${item.estNo}</b> 총 ${item.qty}박스 ${item.warehouse} 
                    </div>
                </div>
                <div class="insert-panel" data-id="${id}"></div>
                <div class="update-panel" data-id="${id}"></div>
                <div class="holding-panel" data-id="${id}"></div>
            </div>
        `;
    });

    sideBox.innerHTML = `
        ${html}
    `;
}

export function renderInsert() {
    const { sideBox } = dom;

    if (!sideBox) return;

    sideBox.innerHTML = `
        <div class="insert-form">
            <div class="insert-list"></div>
        </div>
    `;

    document.querySelector(".insert-list")
        .insertAdjacentHTML("beforeend", createInsertRow());
}

export function createInsertRow() {
    return `
        <div class="insert-row">
            <div class="text">상품명</div>
            <input placeholder="상품명" class="insert-name">

            <div class="text">브랜드</div>
            <input placeholder="브랜드" class="insert-brand">

            <div class="text">등급</div>
            <input placeholder="등급" class="insert-grade">

            <div class="text">ESTNO</div>
            <input placeholder="ESTNO" class="insert-estNo">

            <div class="text">재고</div>
            <input placeholder="재고" class="insert-qty">

            <div class="text">BL</div>
            <input placeholder="BL" class="insert-bl">

            <div class="text">창고</div>
            <input placeholder="창고" class="insert-warehouse">

            <div class="text">유통기한</div>
            <input placeholder="유통기한" class="insert-dueDate">

            <div class = "text">평중</div>
            <input placeholder="평중" class="insert-weight">
            
            <div class = "text">출고일</div>
            <input placeholder="출고일" class="insert-releaseDate">
            
            <div class = "text">홀딩</div>
            <input placeholder="홀딩" class="insert-holding">

            <div class = "text">동결</div>
            <input placeholder="동결" class="insert-frozen">
            
            <div class = "text">사용불가</div>
            <input placeholder="사용불가" class="insert-unuse">
        </div>
        <button class="select-insert-btn">추가</button>
    `;
}

export function renderUpdate() {

    let totalQty = 0;
    let totalWeight = 0;
    state.selectedItems.forEach((item, id) => {
        clearPanels(id);
    });

    state.selectedItems.forEach((item, id) => {

        const target = document.querySelector(
            `.update-panel[data-id="${id}"]`
        );

        if (!target) return;

        target.innerHTML = `
            <div class = "item-btns">
                <button class="select-update-btn" data-id="${id}">수정</button>
                <button class="select-delete-btn" data-id="${id}">삭제</button>
            </div>
            <div class = "update-row" data-id="${id}">
                <div class="text">상품명</div>
                <input value="${item.name}" class="update-name" data-id="${id}">
                <div class="text">브랜드</div>
                <input value="${item.brand}" class="update-brand" data-id="${id}">
                <div class="text">등급</div>
                <input value="${item.grade}" class="update-grade" data-id="${id}">
                <div class="text">ESTNO</div>
                <input value="${item.estNo}" class="update-estNo" data-id="${id}">
                <div class="text">재고</div>
                <input value="${item.qty}" class="update-qty" data-id="${id}">
                <div class="text">BL</div>
                <input value="${item.bl}" class="update-bl" data-id="${id}">
                <div class="text">창고</div>
                <input value="${item.warehouse}" class="update-warehouse" data-id="${id}">
                <div class="text">유통기한</div>
                <input value="${item.dueDate}" class="update-dueDate" data-id="${id}">
                <div class="text">평균중량</div>
                <input value="${item.weight}" class="update-weight" data-id="${id}">
                <div class="text">출고일</div>
                <input value="${item.releaseDate}" class="update-releaseDate" data-id="${id}">
                <div class="text">홀딩</div>
                <input value="${item.holding}" class="update-holding" data-id="${id}">
                <div class="text">동결</div>
                <input value="${item.frozen}" class="update-frozen" data-id="${id}">
                <div class="text">사용불가</div>
                <input value="${item.unuse}" class="update-unuse" data-id="${id}">
                
            </div>
            
        `;

        totalQty += Number(item.qty) || 0;
        totalWeight += Number(item.weight) || 0;
    });
}

export function renderHolding() {

    let total = 0;

    state.selectedItems.forEach((item, id) => {
        clearPanels(id);
    });
    state.selectedItems.forEach((item, id) => {

        const target = document.querySelector(
            `.holding-panel[data-id="${id}"]`
        );

        if (!target) return;

        target.innerHTML = `
            <div class="holding-row" data-id="${id}">
                <div class="text">홀딩개수</div>
                <input class="hold-qty" data-id="${id}" placeholder="개수">
                <div class="text">출고일자</div>
                <input class="hold-releaseDate" data-id="${id}" placeholder="출고일자">
                <div class="text">홀딩자</div>
                <input class="hold-note" data-id="${id}" placeholder="홀딩자">
                <div class="item-btns">
                    <button class="select-holding-btn" data-id="${id}">홀딩</button>
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

    let html = '';

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
            <div class="top-bar">
                <button class="insertRow-btn">행 추가</button>
            </div>
            <div class="footer">
                <button class="all-insert-btn">전체 추가</button>
            </div>
        `
    }

    sideBox.insertAdjacentHTML("beforeend", html);
}
