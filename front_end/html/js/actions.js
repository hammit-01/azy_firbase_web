import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderPanel } from "./panel.js";

export function clearSelection() {

    state.selectedItems.clear();

    renderTable();
    renderPanel();
}
