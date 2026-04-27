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

    state.selectedItems.forEach((item, key) => {
        console.log(key, item);
    });

    let html = "";

    selectedItems.forEach((item, key) => {
        html += `
            <div class="selected-item">
                <b>${item.name}</b><br>
                ${item.brand} / ${item.qty} / ${item.bl}<br>

                <div class="holding-data">
                    <input class="hold-qty" data-key="${key}" placeholder="개수">
                    <input class="hold-date" data-key="${key}" placeholder="날짜">
                    <input class="hold-note" data-key="${key}" placeholder="비고">

                    <div class="item-btns">
                        <button class="cancel-btn" data-key="${key}">취소</button>
                        <button class="holding-btn" data-key="${key}">홀딩</button>
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
            </div>
        </div>
    `;
}
