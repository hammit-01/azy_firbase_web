import { state } from "./state.js";
import { dom } from "./dom.js";

function clearPanels(id) {
    const insert = document.querySelector(`.insert-panel[data-id="${id}"]`);
    const update = document.querySelector(`.update-panel[data-id="${id}"]`);
    const holding = document.querySelector(`.holding-panel[data-id="${id}"]`);

    if (insert) insert.innerHTML = "";
    if (update) update.innerHTML = "";
    if (holding) holding.innerHTML = "";
}

export function renderSelectData() {

    const { sideBox, container } = dom;
    const { selectedItems } = state;

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
        <div class="panel-footer">
            <h4 class="select-no">${selectedItems.size}개 선택</h4>
    `;
}

export function renderInsert() {
    let html = '';

    sideBox.innerHTML = `
        <input placeholder="상품명">
        <input placeholder="브랜드">
        <input placeholder="등급">
        <input placeholder="ESTNO">
        <input placeholder="재고">
        <input placeholder="BL">
        <input placeholder="창고">
        <input placeholder="유통기한">
        <input placeholder="평균">
        <input placeholder="출고일">
        <input placeholder="홀딩">
        <input placeholder="동결">
        <input placeholder="사용불가">
        <button class="all-crud-btn" data-action="">전체 추가</button>
    `;
}

export function renderUpdate() {
    state.selectedItems.forEach((item, id) => {
        clearPanels(id)

        const target = document.querySelector(
            `.update-panel[data-id="${id}"]`
        );

        if (target) {
            target.innerHTML = `
            <input value="${item.name}">
            <input value="${item.brand}">
            <input value="${item.grade}">
            <input value="${item.estNo}">
            <input value="${item.qty}">
            <input value="${item.bl}">
            <input value="${item.warehouse}">
            <input value="${item.dueDate}">
            <input value="${item.weight}">
            <input value="${item.releaseDate}">
            <input value="${item.holding}">
            <input value="${item.frozen}">
            <input value="${item.unuse}">`;
        }
    });

    const sideBox = document.querySelector("#sideBox");
    if (!sideBox.querySelector(".all-crud-btn")) {
        sideBox.insertAdjacentHTML("beforeend", `
                <button class="all-crud-btn" data-action="all-holding">
                    전체 홀딩
                </button>
        `);
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
                    <button class="select-delete-btn">삭제</button>
                </div>
            </div>
        `;
    });

    // 🔥 전체 버튼은 따로!
    const sideBox = document.querySelector("#sideBox");
    if (!sideBox.querySelector(".all-crud-btn")) {
        sideBox.insertAdjacentHTML("beforeend", `
                <button class="all-crud-btn" data-action="all-holding">
                    전체 홀딩
                </button>
        `);
    }
}
