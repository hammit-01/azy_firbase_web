// renderPanel()
function renderPanel() {

    if (!sideBox || !container) return;

    if (selectedItems.size === 0) {
        container.classList.remove("active");
        sideBox.innerHTML = "";
        return;
    }

    container.classList.add("active");

    const html = Array.from(selectedItems.entries()).map(([key, item]) => `
        <div class="selected-item">
            <b>${item.name}</b><br>
            ${item.brand} / ${item.qty} / BL ${item.bl}<br>

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
    `).join("");

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
