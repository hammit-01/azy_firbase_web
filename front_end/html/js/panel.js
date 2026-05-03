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

    state.selectedItems.forEach((item, id) => {
        console.log(id, item);
    });

    let html = '';

    selectedItems.forEach((item, id) => {
        html += `
            <div class="selected-item">
                <div class="item-datas">
                    <button class="cancel-btn" data-id="${id}">X</button>
                    <b>${item.name}</b>
                    ${item.brand} / ${item.qty} / ${item.bl}<br>
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
    let html = '';

    sideBox.innerHTML = `
        <input placeholder="상품명" class="insert-name">
        <input placeholder="브랜드" class="insert-brand">
        <input placeholder="등급" class="insert-grade">
        <input placeholder="ESTNO" class="insert-estNo">
        <input placeholder="수량" class="insert-qty">
        <input placeholder="BL" class="insert-bl">
        <input placeholder="창고" class="insert-warehouse">
        <input placeholder="유통기한" class="insert-dueDate">
        <input placeholder="평중" class="insert-weight">
        <input placeholder="출고일" class="insert-releaseDate">
        <input placeholder="홀딩" class="insert-holding">
        <input placeholder="동결" class="insert-frozen">
        <input placeholder="사용불가" class="insert-unuse">
        <div class="footer">
            <button class="all-insert-btn">전체 추가</button>
        </div>
    `;
}

export function renderUpdate() {
    const updateIds = []
    state.selectedItems.forEach((item, id) => {
        clearPanels(id)

        const target = document.querySelector(
            `.update-panel[data-id="${id}"]`
        );

        if (target) {
            target.innerHTML = `
            <input value="${item.name}" class="update-name" data-id="${id}">
            <input value="${item.brand}" class="update-brand" data-id="${id}">
            <input value="${item.grade}" class="update-grade" data-id="${id}">
            <input value="${item.estNo}" class="update-estNo" data-id="${id}">
            <input value="${item.qty}" class="update-qty" data-id="${id}">
            <input value="${item.bl}" class="update-bl" data-id="${id}">
            <input value="${item.warehouse}" class="update-warehouse" data-id="${id}">
            <input value="${item.dueDate}" class="update-dueDate" data-id="${id}">
            <input value="${item.weight}" class="update-weight" data-id="${id}">
            <input value="${item.releaseDate}" class="update-releaseDate" data-id="${id}">
            <input value="${item.holding}" class="update-holding" data-id="${id}">
            <input value="${item.frozen}" class="update-frozen" data-id="${id}">
            <input value="${item.unuse}" class="update-unuse" data-id="${id}">`;
        }

//        const target = document.querySelector(
//           `.update-panel[data-id="${id}"]`
//        );
//
//        if (!target) return;
//
//        target.innerHTML = `
//                <div class="item-btns">
//                    <button class="select-update-btn" data-id="${id}">수정</button>
//                </div>
//        `;
        
        totalQty += Number(item.qty) || 0;
        totalWeight += Number(item.weight) || 0;
        updateIds.push(id);
    });

    const sideBox = document.querySelector("#sideBox");
    if (!sideBox.querySelector(".all-btn")) {
        sideBox.insertAdjacentHTML("beforeend", `
            <div class="footer">
                <h4 class="select-no">총 ${totalQty} 박스</h4>
                <h4 class="select-no">총 ${totalWeight}kg</h4>
                <button class="all-update-btn" data-id="${updateIds[0]}">전체 수정</button>
            </div>
        `);
        totalQty = 0;
        totalWeight = 0;
    }
}

export function renderHolding() {
    state.selectedItems.forEach((item, id) => {
        clearPanels(id);

        const target = document.querySelector(
            `.holding-panel[data-id="${id}"]`
        );

        if (!target) return;

        target.innerHTML = `
            <div class="holding-data">
                <input class="hold-qty" data-id="${id}" placeholder="개수">
                <input class="hold-date" data-id="${id}" placeholder="날짜">
                <input class="hold-note" data-id="${id}" placeholder="비고">

                <div class="item-btns">
                    <button class="select-holding-btn" data-id="${id}">홀딩</button>
                    <button class="select-delete-btn" data-id="${id}">삭제</button>
                </div>
            </div>
        `;
        
        
    });

    // 🔥 전체 버튼은 따로!
    const sideBox = document.querySelector("#sideBox");
    if (!sideBox.querySelector(".all-btn")) {
        sideBox.insertAdjacentHTML("beforeend", `
            <div class="footer">
                <h4 class="select-no">총 ${total} 박스</h4>
                <button class="all-holding-btn">전체 홀딩</button>
            </div>
        `);
        total = 0;
    }
}
