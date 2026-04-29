import { state } from "./state.js";
import { dom } from "./dom.js";

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
                    <div class="insert-panel"></div>
                </div>

                <!--<div class="holding-data">
                    <input class="hold-qty" data-id="${id}" placeholder="개수">
                    <input class="hold-date" data-id="${id}" placeholder="날짜">
                    <input class="hold-note" data-id="${id}" placeholder="비고">

                    <div class="item-btns">
                        <button class="select-holding-btn" data-id="${id}">홀딩</button>
                        <button class="select-delete-btn">삭제</button>
                    </div>
                </div>-->
            </div>
        `;
    });

    sideBox.innerHTML = `
        ${html}
        <div class="btn">
            <h4 class="select-no">${selectedItems.size}개 선택</h4>
    `;
}

export function renderInsert() {
    const target = document.querySelector('.insert-panel');

    if (!target) {
        return;
    }
    target.innerHTML = `
        <h3>hello</h3>
    `;
    console.log("떴어?");
}
