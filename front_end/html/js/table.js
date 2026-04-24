import { state } from "./state.js";
import { dom } from "./dom.js";

export function renderTable() {
    if (!dom.searchInput) return;

    let data = [...state.allData];

    const keyword = dom.searchInput.value.toLowerCase().trim();
    const field = dom.searchField.value;

    if (keyword) {
        data = data.filter(item =>
            String(item[field] ?? "").toLowerCase().includes(keyword)
        );
    }

    const sortKey = dom.sortField.value;
    const order = dom.sortOrder.value;

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

    dom.listDiv.innerHTML = "";

    data.forEach(item => {

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

        const key =
            `${item.상품명}_${item.ESTNO}_${item.BL번호}_${item.창고}`;

        const checked =
            state.selectedItems.has(key);

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

        if (checked) row.classList.add("selected-row");

        if (isBlocked) {
            row.classList.add("unuse-row");
        } else if (isFreeze) {
            row.classList.add("freezed-row");
        } else if (isHolding) {
            row.classList.add("holding-row");
        }

        dom.listDiv.appendChild(row);
    });
}
