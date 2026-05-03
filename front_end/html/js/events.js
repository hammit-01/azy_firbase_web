import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";
import { renderInsert } from "./panel.js";
import { renderUpdate } from "./panel.js";
import { renderHolding } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData } from "./crud.js";
import { insertData } from "./crud.js";
import { updateData } from "./crud.js";
import { deleteItem } from "./crud.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";

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

    console.log(mode)
    renderAll();

    switch (mode) {
        case "update":
            renderUpdate();
            break;
        case "holding":
            renderHolding();
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
        return;
    }

    // crud menu update section btn
    if (e.target.classList.contains("update-btn")) {
        state.crudMode = null;
        if (state.selectedItems.size === 0) alert("수정할 상품을 선택하세요.");
        else {
            renderUpdate();
            state.crudData = "update";
            return;
        }
    }

    // crud menu holding section btn
    if (e.target.classList.contains("holding-btn")) {
        state.crudMode = null;
        if (state.selectedItems.size === 0) alert("홀딩할 상품을 선택하세요.");
        else {
            renderHolding();
            state.crudData = "holding";
            return;
        }
    }

    // crud menu delete section btn
    if (e.target.classList.contains("select-delete-btn")) {

        const id = e.target.dataset.id;

        if (!id) {console.log("뭔가 이상함:", id); return;}

        state.selectedItems.delete(id);
        await deleteItem(id);

        renderAll();
        renderHolding();
    }

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

        console.log(mode)
        switch (mode) {
            case "update":
                renderAll();
                renderUpdate();
                break;
            case "holding":
                renderAll();
                renderHolding();
                break;
            default:
                renderAll();
        }

        return;
    }


    document.addEventListener("input", (e) => {

        if (e.target.classList.contains("hold-qty")) {

            const total = calculateTotal();

            const totalBox = document.querySelector("#total-box");

            if (totalBox) {
                totalBox.innerText = `총 ${total} 박스`;
            }
        }
    });

    // 데이터 추가 로직
    if (e.target.classList.contains("all-insert-btn")) {

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
    if (e.target.classList.contains("all-update-btn")) {

        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);

        console.log("id:", id);
        console.log(document.querySelector(`.update-name[data-id="${id}"]`));
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
        
        // 새 홀딩 행 id 받기
        const newId = await updateData(item, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, frozen, unuse);

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

    // 홀딩 로직
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