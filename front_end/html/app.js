import { initializeApp } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";
import { getFirestore, collection, onSnapshot } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

// Firebase 설정
const firebaseConfig = {
    apiKey: "AIzaSyBMzVr396MMhlAEwsOfMhVLrOMnRMfWkgQ",
    authDomain: "azy7503-d80d9.firebaseapp.com",
    projectId: "azy7503-d80d9",
};

// Firebase 초기화
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const searchInput = document.getElementById("searchInput");
const searchField = document.getElementById("searchField");
const sortField = document.getElementById("sortField");
const sortOrder = document.getElementById("sortOrder");

console.log("🔥 Firebase 연결 성공");

// 🔥 DOM 로딩 후 실행 (중요)
window.addEventListener("DOMContentLoaded", () => {
    const listDiv = document.getElementById("list");
    listDiv.innerHTML = "<h2>테스트 출력</h2>";

    let allData = [];

    onSnapshot(collection(db, "all_data"), (snapshot) => {

        allData = [];

        snapshot.forEach((doc) => {
            allData.push(doc.data());
        });

        renderTable();
    });

    function renderTable() {

        let data = [...allData];

        // 검색
        const keyword = searchInput.value.toLowerCase();
        const field = searchField.value;

        if (keyword) {
            data = data.filter(item =>
                String(item[field] ?? "").toLowerCase().includes(keyword)
            );
        }

        // 정렬
        const sortKey = sortField.value;
        const order = sortOrder.value;

        data.sort((a, b) => {

            let x = a[sortKey] ?? 0;
            let y = b[sortKey] ?? 0;

            if (sortKey === "유통기한") {
                x = new Date(x);
                y = new Date(y);
            } else {
                x = Number(String(x).replace(/,/g, "")) || 0;
                y = Number(String(y).replace(/,/g, "")) || 0;
            }

            return order === "asc" ? x - y : y - x;
        });

        list.innerHTML = "";

        data.forEach(item => {

            const row = document.createElement("tr");

            row.innerHTML = `
            <td>${item.상품명 ?? ""}</td>
            <td>${item.재고수량 ?? ""}</td>
            <td>${item.브랜드 ?? ""}</td>
            <td>${item.등급 ?? ""}</td>
            <td>${item.ESTNO ?? ""}</td>
            <td>${item.BL번호 ?? ""}</td>
            <td>${item.창고 ?? ""}</td>
            <td>${item.유통기한 ?? ""}</td>
            <td>${item.중량 ?? ""}</td>
            <td>${item.평균중량 ?? ""}</td>
        `;

            list.appendChild(row);
        });
    }

    searchInput.addEventListener("input", renderTable);
    searchField.addEventListener("change", renderTable);
    sortField.addEventListener("change", renderTable);
    sortOrder.addEventListener("change", renderTable);
});
