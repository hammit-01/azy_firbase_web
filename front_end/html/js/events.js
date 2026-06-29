import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData, renderInsert, renderUpdate, renderHolding, renderFooter, createInsertRow } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData, insertData, updateData, deleteItem } from "./crud.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";
import { undoLastAction, undoStack } from "./crud_history.js";
import { insertItem, updateItem, moveHoldingToHistory, deleteHoldingHistory, restoreDoc } from "./firestoreService.js";
import { doc, deleteDoc } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";
import { db } from "./firebase.js";

function showToast(message) {
    let toast = document.getElementById("toast-msg");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast-msg";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), 2000);
}

export function bindEvents() {
    // 드래그 감지 (드래그 중 행 체크 방지)
    let _dragStartX = 0, _dragStartY = 0, _isDragging = false;
    document.addEventListener("mousedown", (e) => {
        _dragStartX = e.clientX;
        _dragStartY = e.clientY;
        _isDragging = false;
    });
    document.addEventListener("mousemove", (e) => {
        if (Math.abs(e.clientX - _dragStartX) > 5 || Math.abs(e.clientY - _dragStartY) > 5) {
            _isDragging = true;
        }
    });

    let searchTimer = null;
    dom.searchInput?.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => renderTable(), 200);
    });

    let filterTimer = null;
    ["show-warehouse", "show-brand", "show-state"].forEach(cls => {
        document.querySelector(`.${cls}`)?.addEventListener("change", () => {
            clearTimeout(filterTimer);
            filterTimer = setTimeout(() => renderTable(), 100);
        });
    });

    document.addEventListener("change", (e) => {
        if (e.target.classList.contains("row-check")) handleChange(e);
    });

    document.addEventListener("input", (e) => {
        if (!e.target.classList.contains("hold-qty")) return;
        const total = calculateTotal();
        const totalBox = document.querySelector("#total-box");
        if (totalBox) totalBox.innerText = `총 ${total} 박스`;
    });

    document.addEventListener("click", handleClick);

    // 더블클릭으로 행 선택
    document.addEventListener("dblclick", (e) => {
        if (e.target.classList.contains("row-check")) return;

        const target = e.target.closest("tr") || e.target.closest(".mobile-card");
        if (!target) return;

        const checkbox = target.querySelector(".row-check");
        if (!checkbox) return;

        const id = checkbox.dataset.id;
        const item = state.allData.find(d => d.id === id);
        if (!item) return;

        if (state.selectedItems.has(id)) {
            state.selectedItems.delete(id);
            if (state.selectedItems.size === 0) state.crudData = null;
        } else {
            addSelectedItem(state, id, item);
        }

        renderAll();
        window.getSelection()?.removeAllRanges();
    });
}

function renderAll() {
    renderTable();
    renderSelectData();
}

function handleChange(e) {
    const id = e.target.dataset.id;
    const item = state.allData.find(d => d.id === id);
    if (!item) return;

    if (e.target.checked) {
        addSelectedItem(state, id, item);
    } else {
        state.selectedItems.delete(id);
    }

    if (state.selectedItems.size === 0) {
        state.crudData = null;
        renderAll();
        return;
    }

    renderAll();

    switch (state.crudData) {
        case "update":
            renderUpdate();
            renderFooter("update");
            break;
        case "holding":
            renderHolding();
            renderFooter("holding");
            break;
        default:
            renderSelectData();
    }
}

async function handleClick(e) {
    // 전체 선택 (현재 필터된 행만)
    if (e.target.classList.contains("select-all")) {
        const visible = state.filteredData.length > 0 ? state.filteredData : state.allData;
        const allChecked = visible.every(item => state.selectedItems.has(item.id));
        state.selectedItems.clear();
        if (!allChecked) {
            visible.forEach(item => addSelectedItem(state, item.id, item));
        }
        renderAll();
        renderSelectData();
        return;
    }

    // 필터 셀렉트 클릭 (change 이벤트 보완용)
    if (
        e.target.classList.contains("show-warehouse") ||
        e.target.classList.contains("show-brand") ||
        e.target.classList.contains("show-state")
    ) {
        setTimeout(() => renderTable(), 0);
        return;
    }

    // 추가 버튼
    if (e.target.classList.contains("insert-btn")) {
        state.selectedItems.clear();
        state.crudData = null;
        renderAll();
        renderInsert();
        renderFooter("insert");
        return;
    }

    // 행 추가
    if (e.target.classList.contains("insertRow-btn")) {
        document.querySelector(".insert-list")?.insertAdjacentHTML("beforeend", createInsertRow());
        return;
    }

    // 홀딩 사용완료
    if (e.target.classList.contains("complete-holding-btn")) {
        const confirmed = confirm("해당 홀딩분 모두 사용 완료 처리 진행합니다.\n계속하시겠습니까?");
        if (!confirmed) return;

        const id       = e.target.dataset.id;
        const recordId = e.target.dataset.recordId;

        // all_data 홀딩 행 백업
        const allDataItem = state.allData.find(v => v.id === id);
        if (!allDataItem) return;
        const allDataBackup = { ...allDataItem };

        try {
            const { historyId, originalData } = await moveHoldingToHistory(recordId, "사용완료");
            await deleteDoc(doc(db, "all_data", id));

            // Undo 저장
            undoStack.push({
                type: "complete-holding",
                undo: async () => {
                    if (historyId) await deleteHoldingHistory(historyId);
                    if (recordId && originalData) await restoreDoc("holding_data", recordId, originalData);
                    const { id: _id, ...restoreData } = allDataBackup;
                    await restoreDoc("all_data", id, restoreData);
                }
            });
            if (undoStack.length > 20) undoStack.shift();

            state.selectedItems.delete(id);
            renderAll();
        } catch (err) {
            console.error("사용완료 처리 실패:", err);
            alert("처리 중 오류가 발생했습니다.");
        }
        return;
    }

    // 추가 카드 제거
    const removeBtn = e.target.closest(".remove-insert-btn, .card-close-btn");
    if (removeBtn && removeBtn.closest(".insert-card")) {
        removeBtn.closest(".insert-card").remove();
        // 카드가 모두 없어지면 패널 닫기
        const remaining = document.querySelectorAll(".insert-card");
        if (remaining.length === 0) {
            dom.container?.classList.remove("active");
            if (dom.sideBox) dom.sideBox.innerHTML = "";
        }
        return;
    }

    // 수정 버튼
    if (e.target.classList.contains("update-btn")) {
        if (state.selectedItems.size === 0) { alert("수정할 상품을 선택하세요."); return; }
        state.crudData = "update";
        renderSelectData();
        renderUpdate();
        renderFooter("update");
        return;
    }

    // 홀딩 버튼
    if (e.target.classList.contains("holding-btn")) {
        if (state.selectedItems.size === 0) { alert("홀딩할 상품을 선택하세요."); return; }
        state.crudData = "holding";
        renderSelectData();
        renderHolding();
        renderFooter("holding");
        return;
    }

    // 전체 취소
    if (e.target.classList.contains("clear-btn")) {
        state.selectedItems.clear();
        state.crudData = null;
        dom.container?.classList.remove("active");
        if (dom.sideBox) dom.sideBox.innerHTML = "";
        renderTable();
        return;
    }

    // 개별 취소
    if (e.target.classList.contains("cancel-btn")) {
        const id = e.target.dataset.id;
        state.selectedItems.delete(id);
        if (state.selectedItems.size === 0) {
            state.crudData = null;
            renderAll();
            return;
        }
        renderAll();
        switch (state.crudData) {
            case "update": renderUpdate(); renderFooter("update"); break;
            case "holding": renderHolding(); renderFooter("holding"); break;
            default: renderAll();
        }
        return;
    }

    // 개별 추가
    if (e.target.classList.contains("select-insert-btn")) {
        const id = e.target.dataset.id;
        const card     = e.target.closest(".insert-card");
        const name     = card?.querySelector(".insert-name")?.value || "";
        const brand    = card?.querySelector(".insert-brand")?.value || "";
        const grade    = card?.querySelector(".insert-grade")?.value || "";
        const estNo    = card?.querySelector(".insert-estNo")?.value || "";
        const qty      = card?.querySelector(".insert-qty")?.value || "";
        const bl       = card?.querySelector(".insert-bl")?.value || "";
        const warehouse = card?.querySelector(".insert-warehouse")?.value || "";
        const dueDate  = card?.querySelector(".insert-dueDate")?.value || "";
        const weight   = card?.querySelector(".insert-weight")?.value || "";
        const releaseDate = card?.querySelector(".insert-releaseDate")?.value || "";
        const holding  = card?.querySelector(".insert-holding")?.value || "";
        const dataState = card?.querySelector(".insert-state")?.value || "";
        const memo     = card?.querySelector(".input-note")?.value || "";

        const newId = await insertData(name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight, releaseDate, holding, dataState, memo);
        if (!newId) return;

        undoStack.push({ type: "insert", undo: async () => { await deleteDoc(doc(db, "all_data", newId)); } });
        if (undoStack.length > 20) undoStack.shift();

        // 해당 카드만 제거, 나머지 카드 유지
        card?.remove();
        renderTable();

        const remainCards = document.querySelectorAll(".insert-card");
        if (remainCards.length === 0) {
            dom.container?.classList.remove("active");
            if (dom.sideBox) dom.sideBox.innerHTML = "";
        }

        showToast("✓ 추가 완료");
        state.flashIds.add(newId);
        setTimeout(() => { state.flashIds.delete(newId); renderTable(); }, 1500);
        return;
    }

    // 개별 수정
    if (e.target.classList.contains("select-update-btn")) {
        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);
        const name     = document.querySelector(`.update-name[data-id="${id}"]`)?.value;
        const brand    = document.querySelector(`.update-brand[data-id="${id}"]`)?.value;
        const grade    = document.querySelector(`.update-grade[data-id="${id}"]`)?.value;
        const estNo    = document.querySelector(`.update-estNo[data-id="${id}"]`)?.value;
        const qty      = document.querySelector(`.update-qty[data-id="${id}"]`)?.value;
        const bl       = document.querySelector(`.update-bl[data-id="${id}"]`)?.value;
        const warehouse = document.querySelector(`.update-warehouse[data-id="${id}"]`)?.value;
        const dueDate  = document.querySelector(`.update-dueDate[data-id="${id}"]`)?.value;
        const weight   = document.querySelector(`.update-weight[data-id="${id}"]`)?.value;
        const releaseDate = document.querySelector(`.update-releaseDate[data-id="${id}"]`)?.value;
        const holding  = document.querySelector(`.update-holding[data-id="${id}"]`)?.value;
        const dataState = document.querySelector(`.update-state[data-id="${id}"]`)?.value;
        const memo     = document.querySelector(`.input-note[data-id="${id}"]`)?.value || "";

        const result = await updateData(item, null, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight, releaseDate, holding, dataState, memo);
        if (!result) return;

        undoStack.push({ type: "update", undo: async () => { await updateItem(result.id, result.prevData); } });
        if (undoStack.length > 20) undoStack.shift();

        state.selectedItems.delete(id);
        state.flashIds.add(result.id);

        if (state.selectedItems.size === 0) {
            state.crudData = null;
            renderAll();
        } else {
            renderAll();
            renderUpdate();
            renderFooter("update");
        }

        showToast("✓ 수정 완료");
        setTimeout(() => { state.flashIds.delete(result.id); renderTable(); }, 1500);
        return;
    }

    // 개별 홀딩
    if (e.target.classList.contains("select-holding-btn")) {
        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);
        const qty  = document.querySelector(`.hold-qty[data-id="${id}"]`)?.value;
        const date = document.querySelector(`.hold-releaseDate[data-id="${id}"]`)?.value;
        const note = document.querySelector(`.hold-note[data-id="${id}"]`)?.value;
        const memo = document.querySelector(`.input-note[data-id="${id}"]`)?.value || "";

        const result = await holdingData(item, Number(qty), date, note, memo);
        if (!result) return;

        undoStack.push({
            type: "holding",
            undo: async () => {
                await updateItem(result.originalId, { 재고: result.originalQty });
                await deleteDoc(doc(db, "all_data", result.holdingId));
                if (result.holdingRecordId) await moveHoldingToHistory(result.holdingRecordId, "취소");
            }
        });
        if (undoStack.length > 20) undoStack.shift();

        state.selectedItems.delete(id);
        state.flashIds.add(result.holdingId);

        if (state.selectedItems.size === 0) {
            state.crudData = null;
            renderAll();
        } else {
            renderAll();
            renderHolding();
            renderFooter("holding");
        }

        showToast("✓ 홀딩 완료");
        setTimeout(() => { state.flashIds.delete(result.holdingId); renderTable(); }, 1500);
        return;
    }

    // 개별 삭제
    if (e.target.classList.contains("select-delete-btn")) {
        const id = e.target.dataset.id;
        const item = state.allData.find(v => v.id === id);
        if (!item) { alert("데이터를 찾을 수 없습니다."); return; }

        const backup = { ...item };
        await deleteItem(item);

        undoStack.push({
            type: "delete",
            undo: async () => {
                const { id: _id, ...restoreData } = backup;
                await insertItem(restoreData);
            }
        });
        if (undoStack.length > 20) undoStack.shift();

        state.selectedItems.delete(id);
        renderAll();
        return;
    }

    // 전체 추가
    if (e.target.classList.contains("all-insert-btn")) {
        const rows = document.querySelectorAll(".insert-card");
        const insertedIds = [];
        for (const row of rows) {
            const newId = await insertData(
                row.querySelector(".insert-name")?.value || "",
                row.querySelector(".insert-brand")?.value || "",
                row.querySelector(".insert-grade")?.value || "",
                row.querySelector(".insert-estNo")?.value || "",
                row.querySelector(".insert-qty")?.value || "",
                row.querySelector(".insert-bl")?.value || "",
                row.querySelector(".insert-warehouse")?.value || "",
                row.querySelector(".insert-dueDate")?.value || "",
                row.querySelector(".insert-weight")?.value || "",
                row.querySelector(".insert-releaseDate")?.value || "",
                row.querySelector(".insert-holding")?.value || "",
                row.querySelector(".insert-state")?.value || "",
                row.querySelector(".input-note")?.value || ""
            );
            if (newId) insertedIds.push(newId);
        }
        undoStack.push({
            type: "bulk-insert",
            undo: async () => { for (const id of insertedIds) await deleteDoc(doc(db, "all_data", id)); }
        });
        if (undoStack.length > 20) undoStack.shift();
        renderAll();
        return;
    }

    // 전체 수정
    if (e.target.classList.contains("all-update-btn")) {
        const rows = document.querySelectorAll(".update-pan[data-id]");
        const backups = [];
        for (const row of rows) {
            const id = row.dataset.id;
            const item = state.allData.find(v => v.id === id);
            const result = await updateData(
                item, id,
                row.querySelector(".update-name")?.value,
                row.querySelector(".update-brand")?.value,
                row.querySelector(".update-grade")?.value,
                row.querySelector(".update-estNo")?.value,
                row.querySelector(".update-qty")?.value,
                row.querySelector(".update-bl")?.value,
                row.querySelector(".update-warehouse")?.value,
                row.querySelector(".update-dueDate")?.value,
                row.querySelector(".update-weight")?.value,
                row.querySelector(".update-releaseDate")?.value,
                row.querySelector(".update-holding")?.value,
                row.querySelector(".update-state")?.value,
                document.querySelector(`.input-note[data-id="${id}"]`)?.value || ""
            );
            if (result) backups.push(result);
        }
        undoStack.push({
            type: "bulk-update",
            undo: async () => { for (const b of backups) await updateItem(b.id, b.prevData); }
        });
        if (undoStack.length > 20) undoStack.shift();
        renderAll();
        return;
    }

    // 전체 홀딩
    if (e.target.classList.contains("all-holding-btn")) {
        const rows = document.querySelectorAll(".holding-pan[data-id]");
        const backups = [];
        for (const row of rows) {
            const id = row.dataset.id;
            const item = state.selectedItems.get(id);
            const result = await holdingData(
                item,
                Number(row.querySelector(".hold-qty")?.value),
                row.querySelector(".hold-releaseDate")?.value,
                row.querySelector(".hold-note")?.value,
                document.querySelector(`.input-note[data-id="${id}"]`)?.value || ""
            );
            if (result) backups.push(result);
        }
        undoStack.push({
            type: "bulk-holding",
            undo: async () => {
                for (const b of backups) {
                    await updateItem(b.originalId, { 재고: b.originalQty });
                    await deleteDoc(doc(db, "all_data", b.holdingId));
                    if (b.holdingRecordId) await moveHoldingToHistory(b.holdingRecordId, "취소");
                }
            }
        });
        if (undoStack.length > 20) undoStack.shift();
        renderAll();
        return;
    }

    // 전체 삭제
    if (e.target.classList.contains("all-delete-btn")) {
        const backups = [];
        for (const [, item] of state.selectedItems) {
            backups.push({ ...item });
            await deleteItem(item);
        }
        undoStack.push({
            type: "bulk-delete",
            undo: async () => {
                for (const backup of backups) {
                    await insertItem({
                        상품명: backup.name || "",
                        브랜드: backup.brand || "",
                        등급: backup.grade || "",
                        ESTNO: backup.estNo || "",
                        재고: backup.qty || 0,
                        BL: backup.bl || "",
                        창고: backup.warehouse || "",
                        유통기한: backup.dueDate || "",
                        평중: backup.weight || 0,
                        출고일: backup.releaseDate || "",
                        홀딩: backup.holding || "",
                        상태: backup.dataState || "",
                        메모: backup.memo || "",
                    });
                }
            }
        });
        if (undoStack.length > 20) undoStack.shift();
        state.selectedItems.clear();
        renderAll();
        return;
    }

    // 되돌리기
    if (e.target.classList.contains("rollback-btn")) {
        await undoLastAction();
        state.selectedItems.clear();
        state.crudData = null;
        renderAll();
        return;
    }

}
