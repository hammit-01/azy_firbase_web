import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { renderInsert } from "./panel.js";
import { renderUpdate } from "./panel.js";
import { renderHolding } from "./panel.js";
import { renderFooter } from "./panel.js";
import { createInsertRow } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData } from "./crud.js";
import { insertData } from "./crud.js";
import { updateData } from "./crud.js";
import { deleteItem } from "./crud.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";
import { undoLastAction } from "./crud_history.js";
import { undoStack } from "./crud_history.js";
import { insertItem } from "./firestoreService.js";
import { updateItem } from "./firestoreService.js";
import { doc, deleteDoc }  from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";
import { db } from "./firebase.js";

export function bindEvents() {

    // =========================
    // input
    // =========================
    dom.searchInput?.addEventListener("input", () => {
        renderTable();
    });

    dom.searchField?.addEventListener("change", () => {
        renderTable();
    });

    // =========================
    // checkbox change
    // =========================
    document.addEventListener("change", handleChange);

    // =========================
    // click
    // =========================
    document.addEventListener("click", handleClick);

    // =========================
    // hold qty 계산
    // =========================
    document.addEventListener("input", (e) => {

        if (
            e.target.classList.contains("hold-qty")
        ) {

            const total =
                calculateTotal();

            const totalBox =
                document.querySelector("#total-box");

            if (totalBox) {

                totalBox.innerText =
                    `총 ${total} 박스`;
            }
        }
    });
}

function renderAll() {
    renderTable();
    renderSelectData();
}

function handleChange(e) {

    if (!e.target.classList.contains("row-check")) return;

    const id = e.target.dataset.id;
    const item = state.allData.find(d => d.id === id);

    if (!item) return;

    if (e.target.checked) {
        addSelectedItem(state, id, item);
    } else {
        state.crudMode = null;
        state.selectedItems.delete(id);
    }

    // 🔥 선택 없으면 초기화
    if (state.selectedItems.size === 0) {
        state.crudMode = null;
        renderSelectData();
        return;
    }

    const mode = state.crudData; // 👉 Map 대신 이거 추천

    renderAll();

    switch (mode) {
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
    // crud menu insert section btn
    if (e.target.classList.contains("insert-btn")) {
        state.crudMode = null;
        if (state.selectedItems.size > 0) {
            const id = e.target.dataset.id;
            const item = state.allData.find(d => d.id === id);
            state.selectedItems.delete(id);
            state.selectedItems.clear();
        }
        
        renderAll();
        renderInsert();
        renderFooter("insert");
        return;
    }
    // 행 추가 로직
    if (e.target.classList.contains("insertRow-btn")) {

        const list = document.querySelector(".insert-list");

        list.insertAdjacentHTML("beforeend", createInsertRow());
    }
    // crud menu update section btn
    if (e.target.classList.contains("update-btn")) {
        if (state.selectedItems.size === 0) alert("수정할 상품을 선택하세요.");
        else {
            state.crudData = "update";
            renderSelectData();
            renderUpdate();
            renderFooter("update");
            return;
        }
    }
    // crud menu holding section btn
    if (e.target.classList.contains("holding-btn")) {
        if (state.selectedItems.size === 0) alert("홀딩할 상품을 선택하세요.");
        else {
            state.crudData = "holding";
            renderSelectData();
            renderHolding();
            renderFooter("holding");
            return;
        }
    }

    // 선택 취소 로직
    // 전체 취소
    if (e.target.classList.contains("clear-btn")) {
        state.selectedItems.clear();
        state.crudMode = null;
        renderAll();
        return;
    }
    // 개별 취소
    if (e.target.classList.contains("cancel-btn")) {

        const id = e.target.dataset.id;

        state.selectedItems.delete(id);

        // 🔥 선택 0개면 종료
        if (state.selectedItems.size === 0) {
            state.crudMode = null;
            renderAll();
            return;
        }

        const mode = state.crudData;

        switch (mode) {
            case "update":
                renderAll();
                renderUpdate();
                renderFooter("update");
                break;
            case "holding":
                renderAll();
                renderHolding();
                renderFooter("holding");
                break;
            default:
                renderAll();
        }

        return;
    }

    // 개별 로직
    // 데이터 추가 로직
    if (e.target.classList.contains("select-insert-btn")) {

        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);

        const name =
            document.querySelector(`.insert-name`).value;

        const brand =
            document.querySelector(`.insert-brand`).value;
        
        const grade =
            document.querySelector(`.insert-grade`).value;
        
        const estNo =
            document.querySelector(`.insert-estNo`).value;

        const qty =
            document.querySelector(`.insert-qty`).value;
        
        const bl =
            document.querySelector(`.insert-bl`).value;

        const warehouse =
            document.querySelector(`.insert-warehouse`).value;

        const dueDate =
            document.querySelector(`.insert-dueDate`).value;
        
        const weight =
            document.querySelector(`.insert-weight`).value;
        
        const releaseDate =
            document.querySelector(`.insert-releaseDate`).value;

        const holding =
            document.querySelector(`.insert-holding`).value;
            
        const frozen =
            document.querySelector(`.insert-frozen`).value;
            
        const unuse =
            document.querySelector(`.insert-unuse`).value;

        // 비고는 뭐임
        //const note =
        //    document.querySelector(`.insert-note`).value;

        // 새 홀딩 행 id 받기
        const newId = await insertData(name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, frozen, unuse);

        undoStack.push({

            type: "insert",

            undo: async () => {

                await deleteDoc(
                    doc(db, "all_data", newId)
                );

            }

        });


        if (undoStack.length > 20) {
            undoStack.shift();
        }
    
        // 체크 해제
        state.selectedItems.delete(id);

        // 강조 대상 저장
        state.flashIds.add(newId);

        renderAll();

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
    // 수정 로직
    if (e.target.classList.contains("select-update-btn")) {

        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);

        const name =
            document.querySelector(`.update-name[data-id="${id}"]`).value;

        const brand =
            document.querySelector(`.update-brand[data-id="${id}"]`).value;

        const grade =
            document.querySelector(`.update-grade[data-id="${id}"]`).value;

        const estNo =
            document.querySelector(`.update-estNo[data-id="${id}"]`).value;

        const qty =
            document.querySelector(`.update-qty[data-id="${id}"]`).value;

        const bl =
            document.querySelector(`.update-bl[data-id="${id}"]`).value;

        const warehouse =
            document.querySelector(`.update-warehouse[data-id="${id}"]`).value;

        const dueDate =
            document.querySelector(`.update-dueDate[data-id="${id}"]`).value;

        const weight =
            document.querySelector(`.update-weight[data-id="${id}"]`).value;

        const releaseDate =
            document.querySelector(`.update-releaseDate[data-id="${id}"]`).value;

        const holding =
            document.querySelector(`.update-holding[data-id="${id}"]`).value;

        const frozen =
            document.querySelector(`.update-frozen[data-id="${id}"]`).value;

        const unuse =
            document.querySelector(`.update-unuse[data-id="${id}"]`).value;

        // 수정 실행
        const result = await updateData(
            item,
            null,
            name,
            brand,
            grade,
            estNo,
            qty,
            bl,
            warehouse,
            dueDate,
            weight,
            releaseDate,
            holding,
            frozen,
            unuse
        );

        if (!result) return;

        // Undo 저장
        undoStack.push({

            type: "update",

            undo: async () => {

                await updateItem(
                    result.id,
                    result.prevData
                );

            }

        });

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        const updatedId = result.id;

        // 체크 해제
        state.selectedItems.delete(id);

        // 강조 대상 저장
        state.flashIds.add(updatedId);

        renderAll();

        // 수정된 행으로 이동
        setTimeout(() => {

            const targetRow =
                document.querySelector(
                    `[data-id="${updatedId}"]`
                );

            if (targetRow) {

                targetRow.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

            }

            state.flashIds.delete(updatedId);

        }, 100);

        // 5초 후 강조 제거
        setTimeout(() => {

            state.flashId = null;

            renderTable();

        }, 5000);

        return;
    }
    // 홀딩 로직
    if (e.target.classList.contains("select-holding-btn")) {

        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);

        const qty =
            document.querySelector(`.hold-qty[data-id="${id}"]`).value;

        const date =
            document.querySelector(`.hold-releaseDate[data-id="${id}"]`).value;

        const note =
            document.querySelector(`.hold-note[data-id="${id}"]`).value;

        const result = await holdingData(
            item,
            Number(qty),
            date,
            note
        );

        if (!result) return;

        // Undo 저장
        undoStack.push({

            type: "holding",

            undo: async () => {

                // 원래 재고 복구
                await updateItem(
                    result.originalId,
                    {
                        재고: result.originalQty
                    }
                );

                // 생성된 홀딩 데이터 삭제
                await deleteDoc(
                    doc(
                        db,
                        "all_data",
                        result.holdingId
                    )
                );

            }

        });

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        // 체크 해제
        state.selectedItems.delete(id);

        // 홀딩으로 생성된 행 ID
        const holdingId = result.holdingId;

        // 강조 대상 저장
        state.flashIds.add(holdingId);

        renderAll();

        setTimeout(() => {

            const targetRow =
                document.querySelector(
                    `[data-id="${holdingId}"]`
                );

            if (targetRow) {

                targetRow.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

            }

            state.flashIds.delete(holdingId);

        }, 100);

        setTimeout(() => {

            state.flashId = null;

            renderTable();

        }, 5000);

        return;
    }
    // 삭제 로직
    if (e.target.classList.contains("select-delete-btn")) {

        const id = e.target.dataset.id;

        // 삭제할 item 찾기
        const item = state.allData.find(v => v.id === id);

        if (!item) {
            alert("데이터를 찾을 수 없습니다.");
            return;
        }

        // 삭제 전 백업
        const backup = { ...item };

        await deleteItem(item);

        // Undo 저장
        undoStack.push({

            type: "delete",

            undo: async () => {

                const { id, ...restoreData } = backup;

                await insertItem(restoreData);

            }

        });

        console.log("item =", item);
        console.log("backup =", backup);

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        state.selectedItems.delete(id);

        renderAll();
        renderHolding();
    }

    // 전체 로직
    if (e.target.classList.contains("all-insert-btn")) {

        const rows = document.querySelectorAll(".insert-row");

        const insertedIds = [];

        for (const row of rows) {

            const name = row.querySelector(".insert-name")?.value || "";
            const brand = row.querySelector(".insert-brand")?.value || "";
            const grade = row.querySelector(".insert-grade")?.value || "";
            const estNo = row.querySelector(".insert-estNo")?.value || "";
            const qty = row.querySelector(".insert-qty")?.value || "";
            const bl = row.querySelector(".insert-bl")?.value || "";
            const warehouse = row.querySelector(".insert-warehouse")?.value || "";
            const dueDate = row.querySelector(".insert-dueDate")?.value || "";
            const weight = row.querySelector(".insert-weight")?.value || "";
            const releaseDate = row.querySelector(".insert-releaseDate")?.value || "";
            const holding = row.querySelector(".insert-holding")?.value || "";
            const frozen = row.querySelector(".insert-frozen")?.value || "";
            const unuse = row.querySelector(".insert-unuse")?.value || "";

            const insertedId = await insertData(
                name,
                brand,
                grade,
                estNo,
                qty,
                bl,
                warehouse,
                dueDate,
                weight,
                releaseDate,
                holding,
                frozen,
                unuse
            );

            if (insertedId) {
                insertedIds.push(insertedId);
            }
        }

        undoStack.push({

            type: "bulk-insert",

            undo: async () => {

                for (const id of insertedIds) {

                    await deleteDoc(
                        doc(db, "all_data", id)
                    );

                }

            }

        });


        if (undoStack.length > 20) {
            undoStack.shift();
        }

        renderAll();

        return;
    }
    if (e.target.classList.contains("all-update-btn")) {
        const rows = document.querySelectorAll(".update-row");

        const backups = [];

        for (const row of rows) {

            const id = row.dataset.id;

            const item = state.allData.find(v => v.id === id);

            const name = row.querySelector(".update-name")?.value;
            const brand = row.querySelector(".update-brand")?.value;
            const grade = row.querySelector(".update-grade")?.value;
            const estNo = row.querySelector(".update-estNo")?.value;
            const qty = row.querySelector(".update-qty")?.value;
            const bl = row.querySelector(".update-bl")?.value;
            const warehouse = row.querySelector(".update-warehouse")?.value;
            const dueDate = row.querySelector(".update-dueDate")?.value;
            const weight = row.querySelector(".update-weight")?.value;
            const releaseDate = row.querySelector(".update-releaseDate")?.value;
            const holding = row.querySelector(".update-holding")?.value;
            const frozen = row.querySelector(".update-frozen")?.value;
            const unuse = row.querySelector(".update-unuse")?.value;

            const result = await updateData(
                item,
                id,
                name,
                brand,
                grade,
                estNo,
                qty,
                bl,
                warehouse,
                dueDate,
                weight,
                releaseDate,
                holding,
                frozen,
                unuse
            );

            if (result) {
                backups.push(result);
            }
        }

        undoStack.push({

            type: "bulk-update",

            undo: async () => {

                for (const backup of backups) {
                    console.log(backup.id)
                    await updateItem(
                        backup.id,
                        backup.prevData
                    );

                }

            }

        });

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        renderAll();

        return;
    }
    if (e.target.classList.contains("all-holding-btn")) {
        const rows = document.querySelectorAll(".holding-row");

        const backups = [];

        for (const row of rows) {

            const id = row.dataset.id;

            const item = state.selectedItems.get(id);

            const qty = row.querySelector(".hold-qty")?.value;

            const releaseDate =
                row.querySelector(".hold-releaseDate")?.value;

            const holding =
                row.querySelector(".hold-note")?.value;

            const result = await holdingData(
                item,
                qty,
                releaseDate,
                holding
            );

            if (result) {
                backups.push(result);
            }
        }

        undoStack.push({

            type: "bulk-holding",

            undo: async () => {

                for (const backup of backups) {

                    // 원래 재고 복구
                    await updateItem(
                        backup.originalId,
                        {
                            재고: backup.originalQty
                        }
                    );

                    // 홀딩 row 삭제
                    await deleteDoc(
                        doc(db, "all_data", backup.holdingId)
                    );
                }

            }

        });

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        renderAll();

        return;
    }
    if (e.target.classList.contains("all-delete-btn")) {
        const backups = [];

        for (const [id, item] of state.selectedItems) {

            backups.push({
                ...item
            });
            
            await deleteItem(item);
        }
        console.log(backups);
        undoStack.push({

            type: "delete",

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
                        동결: backup.frozen || "",
                        사용불가: backup.unuse || ""
                    });

                }

            }

        });

        if (undoStack.length > 20) {
            undoStack.shift();
        }

        state.selectedItems.clear();

        renderAll();

        return;
    }

    // 되돌리기
    if (e.target.classList.contains("rollback-btn")) {

        console.log("undoStack:", undoStack);
        console.log("length:", undoStack.length);

        await undoLastAction();

        // 선택 초기화
        state.selectedItems.clear();

        state.crudMode = null;

        renderAll();
    }

}