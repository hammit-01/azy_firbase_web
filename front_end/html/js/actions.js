import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";

let renderTimer = null;

export function clearSelection() {
    state.selectedItems.clear();

    clearTimeout(renderTimer);
    renderTimer = setTimeout(() => {
        renderTable();
        renderSelectData();
    }, 30);
}
