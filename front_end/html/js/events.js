import { state } from "./state.js";
import { renderTable, updateSortHeaders } from "./table.js";
import { renderSelectData, renderInsert, renderUpdate, renderHolding, renderFooter, createInsertRow } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData, insertData, updateData, deleteItem } from "./crud.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";
import { undoLastAction, pushUndo } from "./crud_history.js";
import { db, fetchAllData, addRenderHook } from "./firebase.js";
import { showToast, showError, showConfirm } from "./ui.js";
import { renderChanges, bindChangesEvents } from "./changes.js";

export function bindEvents() {
    // 변경사항 탭 렌더 훅 등록
    addRenderHook(renderChanges);
    bindChangesEvents();

    // 변경사항 탭 스위칭
    document.querySelector(".changes-tab-btn")?.addEventListener("click", () => {
        const changesEl = document.querySelector(".changes-container");
        const tableEl   = document.querySelector(".table-container");
        const tabBtn    = document.querySelector(".changes-tab-btn");
        const isOpen    = changesEl?.style.display !== "none";

        if (isOpen) {
            changesEl.style.display = "none";
            tableEl.style.display   = "";
            tabBtn.classList.remove("tab-active");
        } else {
            changesEl.style.display = "";
            tableEl.style.display   = "none";
            tabBtn.classList.add("tab-active");
            renderChanges();
        }
    });

    // 출고일·홀딩 hover 카드
    const hoverCard = document.createElement("div");
    hoverCard.id = "hover-info-card";
    document.body.appendChild(hoverCard);

    let _hoveredTr = null;
    const tableEl = document.querySelector(".table-wrap table");
    if (tableEl) {
        tableEl.addEventListener("mouseover", (e) => {
            const tr = e.target.closest("tbody tr");
            if (tr === _hoveredTr) return;
            _hoveredTr = tr;
            if (!tr) { hoverCard.style.display = "none"; return; }
            const 출고일 = tr.dataset.출고일 || "";
            const 홀딩   = tr.dataset.홀딩   || "";
            if (!출고일 && !홀딩) { hoverCard.style.display = "none"; return; }
            hoverCard.innerHTML =
                (출고일 ? `<div><span class="hc-label">출고일</span>${출고일}</div>` : "") +
                (홀딩   ? `<div><span class="hc-label">홀딩</span>${홀딩}</div>`   : "");
            const rect = tr.getBoundingClientRect();
            hoverCard.style.top   = (rect.bottom + 4) + "px";
            hoverCard.style.left  = "auto";
            hoverCard.style.right = (window.innerWidth - rect.right) + "px";
            hoverCard.style.display = "block";
        });
        tableEl.addEventListener("mouseleave", () => {
            _hoveredTr = null;
            hoverCard.style.display = "none";
        });
    }

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

    ["상품명", "브랜드", "등급", "ESTNO", "재고", "BL", "창고", "유통기한", "평중", "메모"].forEach(key => {
        document.querySelector(`th[data-key="${key}"]`)?.addEventListener("click", () => {
            if (state.sortColumn === key) {
                state.sortDir = (state.sortDir + 1) % 3;
                if (state.sortDir === 0) state.sortColumn = null;
            } else {
                state.sortColumn = key;
                state.sortDir = 1;
            }
            renderTable();
        });
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

        const nowChecked = !state.selectedItems.has(id);
        if (nowChecked) {
            addSelectedItem(state, id, item);
        } else {
            state.selectedItems.delete(id);
            if (state.selectedItems.size === 0) state.crudData = null;
        }

        // ① 체크박스·행 클래스만 토글
        checkbox.checked = nowChecked;
        if (target.tagName === "TR") {
            target.classList.toggle("selected-row", nowChecked);
        } else {
            target.classList.toggle("mobile-selected", nowChecked);
        }

        if (state.selectedItems.size === 0) {
            dom.container?.classList.remove("active");
            if (dom.sideBox) dom.sideBox.innerHTML = "";
            window.getSelection()?.removeAllRanges();
            return;
        }

        switch (state.crudData) {
            case "update":
                renderSelectData();
                renderUpdate();
                renderFooter("update");
                break;
            case "holding":
                renderSelectData();
                renderHolding();
                renderFooter("holding");
                break;
            default:
                renderSelectData();
        }

        window.getSelection()?.removeAllRanges();
    });
}

function renderAll() {
    renderTable();
    renderSelectData();
}

function closePanel() {
    state.crudData = null;
    dom.container?.classList.remove("active");
    if (dom.sideBox) dom.sideBox.innerHTML = "";
}

function handleChange(e) {
    const id = e.target.dataset.id;
    const item = state.allData.find(d => d.id === id);
    if (!item) return;

    const checked = e.target.checked;
    if (checked) {
        addSelectedItem(state, id, item);
    } else {
        state.selectedItems.delete(id);
    }

    // ① 해당 행/카드 클래스만 토글 (전체 테이블 재렌더 안 함)
    e.target.closest("tr")?.classList.toggle("selected-row", checked);
    document.querySelector(`.mobile-card[data-id="${id}"]`)?.classList.toggle("mobile-selected", checked);

    if (state.selectedItems.size === 0) {
        state.crudData = null;
        dom.container?.classList.remove("active");
        if (dom.sideBox) dom.sideBox.innerHTML = "";
        return;
    }

    // ② 패널 업데이트 (중복 renderSelectData 제거)
    switch (state.crudData) {
        case "update":
            renderSelectData();
            renderUpdate();
            renderFooter("update");
            break;
        case "holding":
            renderSelectData();
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
        if (state.crudData === "insert" && dom.container?.classList.contains("active")) {
            closePanel();
            return;
        }
        state.selectedItems.clear();
        state.crudData = "insert";
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

    // 추가 카드 제거
    const removeBtn = e.target.closest(".remove-insert-btn, .card-close-btn");
    if (removeBtn && removeBtn.closest(".insert-card")) {
        removeBtn.closest(".insert-card").remove();
        // 카드가 모두 없어지면 패널 닫기
        const remaining = document.querySelectorAll(".insert-card");
        if (remaining.length === 0) {
            closePanel();
        }
        return;
    }

    // 수정 버튼
    if (e.target.classList.contains("update-btn")) {
        if (state.selectedItems.size === 0) { showError("수정할 상품을 선택하세요."); return; }
        if (state.crudData === "update" && dom.container?.classList.contains("active")) {
            closePanel();
            return;
        }
        state.crudData = "update";
        renderSelectData();
        renderUpdate();
        renderFooter("update");
        return;
    }

    // 홀딩 버튼
    if (e.target.classList.contains("holding-btn")) {
        if (state.selectedItems.size === 0) { showError("홀딩할 상품을 선택하세요."); return; }
        if (state.crudData === "holding" && dom.container?.classList.contains("active")) {
            closePanel();
            return;
        }
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

        // 해당 카드만 제거, 나머지 카드 유지
        card?.remove();
        renderTable();

        const remainCards = document.querySelectorAll(".insert-card");
        if (remainCards.length === 0) {
            closePanel();
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
        const qty    = document.querySelector(`.hold-qty[data-id="${id}"]`)?.value;
        const weight = document.querySelector(`.hold-weight[data-id="${id}"]`)?.value;
        const date   = document.querySelector(`.hold-releaseDate[data-id="${id}"]`)?.value;
        const note   = document.querySelector(`.hold-note[data-id="${id}"]`)?.value;
        const memo   = document.querySelector(`.input-note[data-id="${id}"]`)?.value || "";

        const result = await holdingData(item, Number(qty), date, note, memo, weight !== "" ? weight : null);
        if (!result) return;

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
        if (!item) { showError("데이터를 찾을 수 없습니다."); return; }
        if (!await showConfirm("해당 항목을 삭제합니다.\n계속하시겠습니까?")) return;

        await deleteItem(item);

        state.selectedItems.delete(id);
        showToast("✓ 삭제 완료");
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
                row.querySelector(".input-note")?.value || "",
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-insert)로 처리
            );
            if (newId) insertedIds.push(newId);
        }
        pushUndo({ type: "bulk-insert", ids: insertedIds });
        closePanel();
        showToast("✓ 추가 완료");
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
                document.querySelector(`.input-note[data-id="${id}"]`)?.value || "",
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-update)로 처리
            );
            if (result) backups.push(result);
        }
        pushUndo({ type: "bulk-update", backups: backups.map(b => ({ id: b.id, prevData: b.prevData })) });
        showToast("✓ 수정 완료");
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
            const holdWeight = row.querySelector(".hold-weight")?.value;
            const result = await holdingData(
                item,
                Number(row.querySelector(".hold-qty")?.value),
                row.querySelector(".hold-releaseDate")?.value,
                row.querySelector(".hold-note")?.value,
                document.querySelector(`.input-note[data-id="${id}"]`)?.value || "",
                holdWeight !== "" ? holdWeight : null,
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-holding)로 처리
            );
            if (result) backups.push(result);
        }
        pushUndo({ type: "bulk-holding", backups: backups.map(b => ({ originalId: b.originalId, originalQty: b.originalQty, holdingId: b.holdingId, holdingRecordId: b.holdingRecordId })) });
        showToast("✓ 홀딩 완료");
        renderAll();
        return;
    }

    // 전체 삭제
    if (e.target.classList.contains("all-delete-btn")) {
        const count = state.selectedItems.size;
        if (!await showConfirm(`선택한 ${count}건을 삭제합니다.\n계속하시겠습니까?`)) return;
        try {
            const backups = [];
            for (const [, item] of state.selectedItems) {
                backups.push({ ...item });
                await deleteItem(item, true, true);  // noUndo=true, noFetch=true (마지막에 한 번만)
            }
            pushUndo({ type: "bulk-delete", items: backups.map(b => ({
                상품명: b.name || "",
                브랜드: b.brand || "",
                등급: b.grade || "",
                ESTNO: b.estNo || "",
                재고: b.qty || 0,
                BL: b.bl || "",
                창고: b.warehouse || "",
                유통기한: b.dueDate || "",
                평중: b.weight || 0,
                출고일: b.releaseDate || "",
                홀딩: b.holding || "",
                상태: b.dataState || "",
                메모: b.memo || "",
            })) });
            state.selectedItems.clear();
            await fetchAllData();
            showToast("✓ 삭제 완료");
            renderAll();
        } catch (err) {
            console.error("전체 삭제 실패:", err);
            showError("삭제 중 오류가 발생했습니다: " + err.message);
        }
        return;
    }

    // 되돌리기
    if (e.target.classList.contains("rollback-btn")) {
        await undoLastAction();
        state.selectedItems.clear();
        state.crudData = null;
        await fetchAllData();
        return;
    }

}
