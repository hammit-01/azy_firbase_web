import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderPanel } from "./panel.js";

export function bindEvents() {

    document.addEventListener("change", handleChange);
    document.addEventListener("click", handleClick);
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
        state.selectedItems.set(key, item);
    } else {
        state.selectedItems.delete(key);
    }

    renderAll();
}

function handleClick(e) {

    if (!e.target.classList.contains("cancel-btn")) return;

    const key = e.target.dataset.key;

    state.selectedItems.delete(key);

    renderAll();
}
