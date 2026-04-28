import { state } from "./state.js";
import { dom } from "./dom.js";
import { addSelectedItem } from "./data_eda.js";

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

    return value;
}


export function renderTable() {
    if (!dom.searchInput) return;

    let data = [...state.allData];
    const keyword = dom.searchInput.value.toLowerCase().trim();
    const field = dom.searchField.value;
    const sortKey = dom.sortField.value;
    const order = dom.sortOrder.value;


    // 검색
    if (keyword) {
        data = data.filter(item =>
            String(item[field] ?? "").toLowerCase().includes(keyword)
        );
    }

    // 데이터 정렬
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

    // div 표시
    dom.listDiv.innerHTML = "";

    data.forEach(item => {
        const hold = String(item.홀딩 ?? "").trim();
        const isFreeze = item.동결 === true;
        const isBlocked = item.사용불가 === true;
        const id = item.id;
        const checked = state.selectedItems.has(id);
        const row = document.createElement("tr");
        const isHolding =
            hold !== "" &&
            hold !== "false" &&
            hold !== "null" &&
            hold !== "None" &&
            hold !== "nan" &&
            hold !== "NaT";

        row.innerHTML = `
            <td>
                <input type="checkbox"
                    class="row-check"
                    data-id="${item.id}"
                    ${checked ? "checked" : ""}>
            </td>
            <td>${safeValue(item.상품명 ?? null)}</td>
            <td>${safeValue(item.브랜드 ?? null)}</td>
            <td>${safeValue(item.등급 ?? null)}</td>
            <td>${safeValue(item.ESTNO ?? null)}</td>
            <td>${safeValue(item.재고 ?? null)}</td>
            <td>${safeValue(item.BL ?? null)}</td>
            <td>${safeValue(item.창고 ?? null)}</td>
            <td>${safeValue(item.유통기한 ?? null)}</td>
            <td>${safeValue(item.평중 ?? null)}</td>
            <td>${safeValue(item.출고일 ?? null)}</td>
            <td>${safeValue(item.홀딩 ?? null)}</td>
        `;

        if (checked) row.classList.add("selected-row");

        if (isBlocked) {
            row.classList.add("unuse-row");
        } else if (isFreeze) {
            row.classList.add("freezed-row");
        } else if (isHolding) {
            row.classList.add("holding-row");
        }

        // 홀딩 행 일시 표시 및 포커스
        if (state.flashIds.has(item.id)) {
            row.classList.add("flash-row");
        }

        dom.listDiv.appendChild(row);
    });
}
