import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderPanel } from "./panel.js";

export function clearSelection() {
    // 체크박스 전체 취소 클릭시 selectedItems map 모두 삭제
    state.selectedItems.clear();

    // 삭제후 재랜더링
    renderTable();
    renderPanel();
}
