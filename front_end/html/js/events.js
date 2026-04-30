import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { renderInsert } from "./panel.js";
import { renderUpdate } from "./panel.js";
import { renderHolding } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData } from "./crud.js";
import { dom } from "./dom.js";


export function bindEvents() {

    document.addEventListener("change", handleChange);
    document.addEventListener("click", handleClick);
    
    dom.searchInput.addEventListener("input", renderTable);
    dom.searchField.addEventListener("change", renderTable);
    dom.sortField.addEventListener("change", renderTable);
    dom.sortOrder.addEventListener("change", renderTable);
}

function renderAll() {
    renderTable();
    renderSelectData();
}

function handleChange(e) {
    const id = e.target.dataset.id;
    const item = state.allData.find(d => d.id === id);
    const crudData_state = state.crudData.get("crud");

    if (!e.target.classList.contains("row-check")) return;

    if (!item) return;

    if (e.target.checked) {
        addSelectedItem(state, id, item);
    } else {
        state.selectedItems.delete(id);
    }

    if (crudData_state === "update") {
        renderAll();
        renderUpdate();
    }
    else if (crudData_state === "holding") {
        renderAll();
        renderHolding();
    } else renderSelectData();
}

async function handleClick(e) {
    // crud insert section btn
    if (e.target.classList.contains("insert-btn")) {
        state.crudData.clear();
        if (state.selectedItems.size > 0) {
            const id = e.target.dataset.id;
            const item = state.allData.find(d => d.id === id);
            state.selectedItems.delete(id);
            state.selectedItems.clear();
        }
        
        renderAll();
        renderInsert();
        return;
    }

    // crud update section btn
    if (e.target.classList.contains("update-btn")) {
        state.crudData.clear();
        if (state.selectedItems.size === 0) alert("수정할 상품을 선택하세요.");
        else {
            renderUpdate();
            state.crudData.set("crud","update")
            return;
        }
    }

    // crud holding section btn
    if (e.target.classList.contains("holding-btn")) {
        state.crudData.clear();
        if (state.selectedItems.size === 0) alert("홀딩할 상품을 선택하세요.");
        else {
            renderHolding();
            state.crudData.set("crud","holding")
            return;
        }
    }

    // 전체 취소
    if (e.target.classList.contains("clear-btn")) {
        state.selectedItems.clear();
        state.crudData.clear();
        renderAll();
        return;
    }

    // 개별 취소
    if (e.target.classList.contains("cancel-btn")) {
        const id = e.target.dataset.id;
        const crudData_state = state.crudData.get("crud");

        state.selectedItems.delete(id);

        if (crudData_state === "update") {
            renderAll();
            renderUpdate();
        }
        else if (crudData_state === "holding") {
            renderAll();
            renderHolding();
        }
        return;
    }

    if (e.target.classList.contains("select-holding-btn")) {

        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);

        const qty =
            document.querySelector(`.hold-qty[data-id="${id}"]`).value;

        const date =
            document.querySelector(`.hold-date[data-id="${id}"]`).value;

        const note =
            document.querySelector(`.hold-note[data-id="${id}"]`).value;

        // 새 홀딩 행 id 받기
        const newId = await holdingData(item, Number(qty), date, note);

        // 체크 해제
        state.selectedItems.delete(id);

        // 강조 대상 저장
        state.flashIds.add(newId);

        renderAll();
        renderHolding();

        console.log("홀딩중!!!!!");

        // 새 행으로 스크롤 이동
        setTimeout(() => {
            const targetRow =
                document.querySelector(`[data-id="${newId}"]`)


            if (targetRow) {
                targetRow.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            }
            state.flashIds.delete(newId);
        }, 100);

        // 5초 후 강조 제거
        setTimeout(() => {
            state.flashId = null;
            renderTable();
        }, 5000);
    
    }

}