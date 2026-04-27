import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderPanel } from "./panel.js";
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
    renderPanel();
}

function handleChange(e) {

    if (!e.target.classList.contains("row-check")) return;

    const key = e.target.dataset.key;
    
    const item = state.allData.find(d =>
        `${d.상품명}_${d.ESTNO}_${d.BL번호}_${d.창고}` === key
    );

    if (!item) return;

    if (e.target.checked) {
        addSelectedItem(state, key, item);
    } else {
        state.selectedItems.delete(key);
    }

    renderAll();
}

async function handleClick(e) {

    // 전체 취소
    if (e.target.classList.contains("clear-btn")) {
        state.selectedItems.clear();
        renderAll();
        return;
    }

    // 개별 취소
    if (e.target.classList.contains("cancel-btn")) {
        const key = e.target.dataset.key;

        state.selectedItems.delete(key);

        renderAll();
        return;
    }

    if (e.target.classList.contains("holding-btn")) {

        const key = e.target.dataset.key;
        const item = state.selectedItems.get(key);

        const qty =
            document.querySelector(`.hold-qty[data-key="${key}"]`).value;

        const date =
            document.querySelector(`.hold-date[data-key="${key}"]`).value;

        const note =
            document.querySelector(`.hold-note[data-key="${key}"]`).value;

        await holdingData(item, Number(qty), date, note);
    }
}