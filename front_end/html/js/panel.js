import { state } from "./state.js";
import { dom } from "./dom.js";

export function renderPanel() {

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

    let html = '<button class="insert">추가</button>';

    selectedItems.forEach((item, id) => {
        html += `
            <div class="selected-item">
                <b>${item.name}</b><br>
                ${item.brand} / ${item.qty} / ${item.bl}<br>

                <div class="holding-data">
                    <button class="cancel-btn" data-id="${id}">X</button>
                    <input class="hold-qty" data-id="${id}" placeholder="개수">
                    <input class="hold-date" data-id="${id}" placeholder="날짜">
                    <input class="hold-note" data-id="${id}" placeholder="비고">

                    <div class="item-btns">
                        <button class="holding-btn" data-id="${id}">홀딩</button>
                    </div>
                </div>
            </div>
        `;
    });

    sideBox.innerHTML = `
        ${html}
        <div class="btn">
            <h4 class="select-no">${selectedItems.size}개 선택</h4>

            <div class="btn-group">
                <button class="clear-btn" data-action="clear-selection">전체 취소</button>
                <button class="all-holding-btn" data-action="all-holding">전체 홀딩</button>

                <div class="crud-selction">
                    <button class="update">수정</button>
                    <button class="delete">삭제</button>
                </div>
            </div>
        </div>
    `;
}
