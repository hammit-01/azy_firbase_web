import { initializeApp } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";
import { getFirestore, collection, onSnapshot } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";
import { bindHoldingEvents } from "./holding_js.js";

const firebaseConfig = {
    apiKey: "AIza...",
    authDomain: "azy7503-d80d9.firebaseapp.com",
    projectId: "azy7503-d80d9",
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

let allData = [];
const selectedItems = new Map();

// DOM
let searchInput, searchField, sortField, sortOrder, listDiv, container, sideBox;

window.addEventListener("DOMContentLoaded", () => {

    searchInput = document.getElementById("searchInput");
    searchField = document.getElementById("searchField");
    sortField = document.getElementById("sortField");
    sortOrder = document.getElementById("sortOrder");
    listDiv = document.getElementById("list");
    container = document.querySelector(".container");
    sideBox = document.getElementById("sideBox");

    onSnapshot(collection(db, "all_data"), (snapshot) => {
        allData = snapshot.docs.map(d => d.data());
        renderTable();
        renderPanel();
    });
    bindHoldingEvents(db, selectedItems, renderTable, renderPanel);

    searchInput.addEventListener("input", renderTable);
    searchField.addEventListener("change", renderTable);
    sortField.addEventListener("change", renderTable);
    sortOrder.addEventListener("change", renderTable);
    

});


// ================= TABLE =================
function renderTable() {

    let data = [...allData];

    const keyword = searchInput.value.toLowerCase().trim();
    const field = searchField.value;

    if (keyword) {
        data = data.filter(item =>
            String(item[field] ?? "").toLowerCase().includes(keyword)
        );
    }

    const sortKey = sortField.value;
    const order = sortOrder.value;

    data.sort((a, b) => {
        let x = a[sortKey] ?? 0;
        let y = b[sortKey] ?? 0;

        if (sortKey === "유통기한") {
            x = new Date(x);
            y = new Date(y);
        } else {
            x = Number(x) || 0;
            y = Number(y) || 0;
        }

        return order === "asc" ? x - y : y - x;
    });

    listDiv.innerHTML = "";

    data.forEach(item => {
        // 홀딩 있으면 true
        const hold = String(item.홀딩 ?? "").trim();
        const isHolding =
            hold !== "" &&
            hold !== "false" &&
            hold !== "null" &&
            hold !== "None" &&
            hold !== "nan" &&
            hold !== "NaT";
        const isFreeze = item.동결 === true;
        const isBlocked = item.사용불가 === true;

        const key = `${item.상품명}_${item.ESTNO}_${item.BL번호}_${item.창고}`;
        const checked = selectedItems.has(key);

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <input type="checkbox"
                    class="row-check"
                    data-key="${key}"
                    ${checked ? "checked" : ""}>
            </td>
            <td>${item.상품명 ?? ""}</td>
            <td>${item.브랜드 ?? ""}</td>
            <td>${item.등급 ?? ""}</td>
            <td>${item.ESTNO ?? ""}</td>
            <td>${item.재고수량 ?? ""}</td>
            <td>${item.BL번호 ?? ""}</td>
            <td>${item.창고 ?? ""}</td>
            <td>${item.유통기한 ?? ""}</td>
            <td>${item.중량 ?? ""}</td>
            <td>${item.평균중량 ?? ""}</td>
            <td>${item.출고예정일 ?? ""}</td>
            <td>${item.홀딩 ?? ""}</td>
        `;

        if (checked) {
            row.classList.add("selected-row");
        }

        // 우선순위 적용
        if (isBlocked) {
            row.classList.add("unuse-row");
        } else if (isFreeze) {
            row.classList.add("freezed-row");
        } else if (isHolding) {
            row.classList.add("holding-row");
        }

        listDiv.appendChild(row);
    });
}


// ================= CHECK =================
document.addEventListener("change", (e) => {

    if (!e.target.classList.contains("row-check")) return;

    const row = e.target.closest("tr");
    const key = e.target.dataset.key;

    const item = {
        name: row.children[1].innerText,
        brand: row.children[2].innerText,
        qty: row.children[5].innerText,
        bl: row.children[6].innerText
    };

    if (e.target.checked) {
        selectedItems.set(key, item);
        row.classList.add("selected-row");
    } else {
        selectedItems.delete(key);
        row.classList.remove("selected-row");
    }

    renderPanel();
});


// ================= PANEL =================
function renderPanel() {

    if (!sideBox || !container) return;

    if (selectedItems.size === 0) {
        container.classList.remove("active");
        sideBox.innerHTML = "";
        return;
    }

    container.classList.add("active");

    // let html = `
    //     <button class="clear-btn" onclick="clearSelection()">전체 취소</button>
    //     <h3>선택 ${selectedItems.size}</h3>
    //     <hr>
    // `;

    let html = ''

    selectedItems.forEach((item, key) => {

        html += `
            <div class="selected-item">
                <b>${item.name}</b><br>
                ${item.brand} / ${item.qty} / BL ${item.bl}<br>

                <input class="hold-qty" data-key="${key}" placeholder="개수">
                <input class="hold-date" data-key="${key}" placeholder="날짜">
                <input class="hold-note" data-key="${key}" placeholder="비고">
                <button class="holding-btn" data-key="${key}">홀딩</button>
            </div>
        `;
    });

    html += `
        <div class="btn">
            <h4 class="select-no">${selectedItems.size}개 선택</h4>

            <div class="btn-group">
                <button class="clear-btn" onclick="clearSelection()">전체 취소</button>
                <button class="all-holding-btn">전체 홀딩</button>
            </div>
        </div>

    `
    sideBox.innerHTML = html;
}


// ================= CLEAR =================
function clearSelection() {

    selectedItems.clear();

    document.querySelectorAll(".row-check").forEach(c => c.checked = false);
    document.querySelectorAll(".selected-row").forEach(r => r.classList.remove("selected-row"));

    renderPanel();
}

window.clearSelection = clearSelection;
