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
                <div class="holding-panel" data-id="${id}" style="align-items: flex-end;"></div>
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
        <div class="top-bar">
            <button class="insertRow-btn">행 추가</button>
        </div>
        <div class="insert-list"></div>
    `;

    document.querySelector(".insert-list")
        .insertAdjacentHTML("beforeend", createInsertRow());
}

export function createInsertRow() {
    return `
        <div class="insert-pan">
            <div>
                <div class="text">상품명</div>
                <input type="text" placeholder="상품명" class="insert-name" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div>
            <div class="text">브랜드</div>
            <input type="text" placeholder="브랜드" class="insert-brand" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div style="width:80px;">
            <div class="text">등급</div>
            <input type="text" placeholder="등급" class="insert-grade" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div style="width:80px;">
            <div class="text">ESTNO</div>
            <input type="text" placeholder="ESTNO" class="insert-estNo" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div style="width:80px;">
            <div class="text">재고</div>
            <input type="number" placeholder="재고" class="insert-qty" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div style="width:170px;">
            <div class="text">BL</div>
            <input type="text" placeholder="BL" class="insert-bl" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div>
            <div class="text">창고</div>
            <input type="text" placeholder="창고" class="insert-warehouse" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div>
            <div class="text">유통기한</div>
            <input type="date" placeholder="유통기한" class="insert-dueDate" id="input-box" style="background-color: #d6ffc2;">
            </div>

            <div style="width:80px;">
            <div class = "text">평중</div>
            <input type="number" placeholder="평중" class="insert-weight" id="input-box" style="background-color: #d6ffc2;">
            </div>
            
            <div>
            <div class = "text">출고일</div>
            <input type="date" placeholder="출고일" class="insert-releaseDate" id="input-box">
            </div>
            
            <div style="width:140px;">
            <div class = "text">홀딩</div>
            <input type="text" placeholder="홀딩" class="insert-holding" id="input-box">
            </div>

            <div style="width:80px;">
            <div class = "text">상태</div>
            <form action="#">
                <select class="insert-state" id="input-box">
                    <option value="non">없음</option>
                    <option value="freeze">동결</option>
                    <option value="stopped">사용불가</option>
                    <option value="moving">이고</option>
                </select>
            </form>
            </div>
        </div>
        <div class="note">
            <input type="text" class="input-note" placeholder="메모">
            <button class="select-insert-btn">추가</button>
        </div>
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
        const dataState = item.dataState || "";
        console.log(item);
        console.log(item.dataState);
        console.log(item.상태);

        if (!target) return;

        target.innerHTML = `
            <div class = "update-pan" data-id="${id}">
                <div>
                    <div class="text">상품명</div>
                    <input type="text" value="${item.name}" class="update-name" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div>
                    <div class="text">브랜드</div>
                    <input type="text" value="${item.brand}" class="update-brand" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div style="width:80px;">
                    <div class="text">등급</div>
                    <input type="text" value="${item.grade}" class="update-grade" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div style="width:80px;">
                    <div class="text">ESTNO</div>
                    <input type="text" value="${item.estNo}" class="update-estNo" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div style="width:80px;">
                    <div class="text">재고</div>
                    <input type="number" value="${item.qty}" class="update-qty" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>
                <div style="width:170px;">
                    <div class="text">BL</div>
                    <input type="text" value="${item.bl}" class="update-bl" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div>
                    <div class="text">창고</div>
                    <input type="text" value="${item.warehouse}" class="update-warehouse" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div>
                    <div class="text">유통기한</div>
                    <input type="date" value="${item.dueDate}" class="update-dueDate" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div style="width:80px;">
                    <div class="text">평중</div>
                    <input type="number" value="${item.weight}" class="update-weight" data-id="${id}" id="input-box" style="background-color: #d6ffc2;">
                </div>

                <div>
                    <div class="text">출고일</div>
                    <input type="date" value="${item.releaseDate}" class="update-releaseDate" data-id="${id}" id="input-box">
                </div>

                <div style="width:140px;">
                    <div class="text">홀딩</div>
                    <input type="text" value="${item.holding}" class="update-holding" data-id="${id}" id="input-box">
                </div>

                <div style="width:80px;">
                    <div class="text">상태</div>
                    <select class="update-state" data-id="${id}" id="input-box">
                        <option value="non" ${dataState === "non" ? "selected" : ""}>없음</option>
                        <option value="freeze" ${dataState === "freeze" ? "selected" : ""}>동결</option>
                        <option value="stopped" ${dataState === "stopped" ? "selected" : ""}>사용불가</option>
                        <option value="moving" ${dataState === "moving" ? "selected" : ""}>이고</option>
                    </select>
                </div>
            </div>

            <div class="note">
                <input type="text" class="input-note" data-id="${id}" placeholder="메모" value="${item.memo || ""}">
            <div>
            <div class = "item-btns">
                <button class="select-update-btn" data-id="${id}">수정</button>
                <button class="select-delete-btn" data-id="${id}">삭제</button>
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
            <div class="holding-pan" data-id="${id}" style="flex-wrap: nowrap;">
                <div>
                    <div class="text">홀딩개수</div>
                    <input type="number" class="hold-qty" data-id="${id}" placeholder="개수" id="input-box">
                </div>

                <div>
                    <div class="text">출고일자</div>
                    <input type="date" class="hold-releaseDate" data-id="${id}" placeholder="출고일자" id="input-box">
                </div>

                <div>
                    <div class="text">홀딩자</div>
                    <input type="text" class="hold-note" data-id="${id}" placeholder="홀딩자" id="input-box">
                </div>               
            </div>
            <div class="note"  style="height: 50%; display: flex; flex-direction: row; align-content: flex-end; justify-content: flex-start; gap: 10px">
                <input type="text" class="input-note" data-id="${id}" placeholder="메모" value="${item.memo}">
                <div class="item-btns" style="display: flex; justify-content: flex-start;">
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
            <div class="footer">
                <button class="all-insert-btn">전체 추가</button>
            </div>
        `
    }

    sideBox.insertAdjacentHTML("beforeend", html);
}
