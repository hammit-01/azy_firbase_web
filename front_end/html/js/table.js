import { state } from "./state.js";
import { dom } from "./dom.js";

function safeValue(value) {
    const v = String(value ?? "").trim();

    if (
        v === "" ||
        v === "nan" ||
        v === "NaN" ||
        v === "null" ||
        v === "undefined" ||
        v === "None" ||
        v === "NaT"
    ) {
        return "";
    }

    return v;
}

export function renderTableSize(count, size, mean) {

    const target = document.querySelector(".table_size");

    if (!target) return;

    target.textContent =
        `총 ${count} 행 / 총 ${size} 박스 / 총 ${mean.toFixed(2)} KG`;
}

export function renderTable() {
    if (!dom.searchInput) return;

    let data = [...state.allData];

    const keyword = dom.searchInput.value.toLowerCase().trim();
    const field = dom.searchField.value;
    const statusField = dom.sortField2?.value;
    const sortKey = dom.sortField.value;
    const order = dom.sortOrder.value;

    // =========================
    // 1. 상태 필터 (동결 / 홀딩)
    // =========================
    if (statusField && statusField !== "전체") {
        data = data.filter(item => {

            if (statusField === "동결") {
                return item.동결 != null &&
                    String(item.동결).trim() !== "" &&
                    String(item.동결).toLowerCase() !== "nan";
            }

            if (statusField === "홀딩") {
                const hold = String(item.홀딩 ?? "").trim();
                return hold !== "" &&
                    hold !== "nan" &&
                    hold !== "NaN" &&
                    hold !== "null";
            }

            return true;
        });
    }

    // =========================
    // 2. 검색 필터
    // =========================
    if (keyword) {
        data = data.filter(item => {

            if (field === "전체") {
                return Object.values(item).some(value => {
                    if (value == null) return false;
                    if (typeof value === "object") return false;

                    return String(value)
                        .toLowerCase()
                        .includes(keyword);
                });
            }

            return String(item[field] ?? "")
                .toLowerCase()
                .includes(keyword);
        });
    }

    // =========================
    // 3. 정렬
    // =========================
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

    // =========================
    // 4. 렌더링
    // =========================
    dom.listDiv.innerHTML = "";

    data.forEach(item => {

        const id = item.id;
        const checked = state.selectedItems.has(id);

        const hold = String(item.홀딩 ?? "").trim();

        const isFreeze =
            item.동결 != null &&
            String(item.동결).trim() !== "" &&
            String(item.동결).toLowerCase() !== "nan";

        const isBlocked =
            item.사용불가 != null &&
            String(item.사용불가).trim() !== "" &&
            String(item.사용불가).toLowerCase() !== "nan";

        const isHolding =
            hold &&
            hold !== "nan" &&
            hold !== "NaN" &&
            hold !== "null";

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <input type="checkbox"
                    class="row-check"
                    data-id="${id}"
                    ${checked ? "checked" : ""}>
            </td>
            <td>${safeValue(item.상품명)}</td>
            <td>${safeValue(item.브랜드)}</td>
            <td>${safeValue(item.등급)}</td>
            <td>${safeValue(item.ESTNO)}</td>
            <td>${safeValue(item.재고)}</td>
            <td>${safeValue(item.BL)}</td>
            <td>${safeValue(item.창고)}</td>
            <td>${safeValue(item.유통기한)}</td>
            <td>${safeValue(item.평중)}</td>
            <td>${safeValue(item.출고일)}</td>
            <td>${safeValue(item.홀딩)}</td>
        `;

        // =========================
        // 5. row 상태 UI
        // =========================
        if (checked) row.classList.add("selected-row");

        if (isBlocked) {
            row.classList.add("unuse-row");
        } else if (isFreeze) {
            row.classList.add("freezed-row");
        } else if (isHolding) {
            row.classList.add("holding-row");
        }

        if (state.flashIds.has(id)) {
            row.classList.add("flash-row");
        }

        dom.listDiv.appendChild(row);
    });
    
    const totalWeight = data.reduce((sum, item) => {
        return sum + (Number(item.재고) || 0);
    }, 0);
    const mean = data.reduce((sum, item) => {
        return sum + (Number(item.평중) || 0);
    }, 0);

    renderTableSize(data.length, totalWeight, mean);
}
