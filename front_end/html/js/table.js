import { state } from "./state.js";
import { dom } from "./dom.js";

// =========================
// render debounce
// =========================
let renderTimer = null;

export function requestRender() {

    clearTimeout(renderTimer);

    renderTimer = setTimeout(() => {
        renderTable();
    }, 30);
}

function parseDate(value) {

    if (!value) {
        return new Date("9999-12-31");
    }

    return new Date(
        String(value)
            .replaceAll(".", "-")
            .replaceAll(" ", "")
    );
}

// =========================
// 안전 값
// =========================
function safeValue(value) {

    const v = cleanText(value);

    if (
        v === "" ||
        v.toLowerCase() === "nan" ||
        v === "null" ||
        v === "undefined" ||
        v === "None" ||
        v === "NaT"
    ) {
        return "";
    }

    return v;
}

// =========================
// 문자열 정리
// =========================
function cleanText(value) {

    return String(value ?? "")
        .replace(/\u200B/g, "") // zero-width
        .replace(/\*/g, "")
        .trim();
}

// =========================
// 문자열 비교
// =========================
function compareText(a, b, order = "asc") {

    const x = cleanText(a);
    const y = cleanText(b);

    return order === "asc"

        ? x.localeCompare(
            y,
            "ko-KR",
            {
                numeric: true,
                sensitivity: "base"
            }
        )

        : y.localeCompare(
            x,
            "ko-KR",
            {
                numeric: true,
                sensitivity: "base"
            }
        );
}

// =========================
// 숫자 비교
// =========================
function compareNumber(a, b, order = "asc") {

    const x =
        Number(
            cleanText(a)
                .replaceAll(",", "")
        );

    const y =
        Number(
            cleanText(b)
                .replaceAll(",", "")
        );

    return order === "asc"
        ? x - y
        : y - x;
}

// =========================
// 날짜 비교
// =========================
function compareDate(a, b, order = "asc") {

    const x =
        a
            ? Date.parse(cleanText(a))
            : Infinity;

    const y =
        b
            ? Date.parse(cleanText(b))
            : Infinity;

    return order === "asc"
        ? x - y
        : y - x;
}

// =========================
// 테이블 사이즈
// =========================
export function renderTableSize(
    count,
    size,
    mean
) {

    const target =
        document.querySelector(".table_size");

    if (!target) return;

    target.textContent =
        `총 ${count} 행 / 총 ${size} 박스 / 총 ${mean.toFixed(2)} KG`;
}

// =========================
// 테이블 렌더
// =========================
export function renderTable() {

    if (!dom.searchInput) return;

    let data = [...state.allData];

    const keyword =
        cleanText(
            dom.searchInput.value
        ).toLowerCase();

    const field =
        dom.searchField.value;

    const statusField =
        dom.sortField2?.value;

    // =========================
    // 상태 필터
    // =========================
    if (
        statusField &&
        statusField !== "전체"
    ) {

        data = data.filter(item => {

            // 동결
            if (statusField === "동결") {

                return cleanText(item.동결) !== "";
            }

            // 홀딩
            if (statusField === "홀딩") {

                return cleanText(item.홀딩) !== "";
            }

            return true;
        });
    }

    // =========================
    // 검색 필터
    // =========================
    if (keyword) {

        data = data.filter(item => {

            // 전체 검색
            if (field === "전체") {

                return Object.values(item)
                    .some(value => {

                        if (value == null)
                            return false;

                        if (
                            typeof value === "object"
                        )
                            return false;

                        return cleanText(value)
                            .toLowerCase()
                            .includes(keyword);
                    });
            }

            // 컬럼 검색
            return cleanText(item[field])
                .toLowerCase()
                .includes(keyword);
        });
    }

    // =========================
    // 빈 상품 제거
    // =========================
    data = data.filter(item => {

        return cleanText(item.상품명) !== "";
    });

    // =========================
    // 정렬
    // =========================
    data.sort((a, b) => {

        // 상품명
        let result = String(a["상품명"] ?? "")
            .trim()
            .localeCompare(
                String(b["상품명"] ?? "").trim(),
                "ko-KR",
                { numeric: true }
            );

        if (result !== 0) return result;

        // 브랜드
        result = String(a["브랜드"] ?? "")
            .trim()
            .localeCompare(
                String(b["브랜드"] ?? "").trim(),
                "ko-KR",
                { numeric: true }
            );

        if (result !== 0) return result;

        // 등급
        result = String(a["등급"] ?? "")
            .trim()
            .localeCompare(
                String(b["등급"] ?? "").trim(),
                "ko-KR",
                { numeric: true }
            );

        if (result !== 0) return result;

        // ESTNO
        result = String(a["ESTNO"] ?? "")
            .trim()
            .localeCompare(
                String(b["ESTNO"] ?? "").trim(),
                "ko-KR",
                { numeric: true }
            );

        if (result !== 0) return result;

        // 유통기한
        const x = parseDate(a["유통기한"]);
        const y = parseDate(b["유통기한"]);

        return x - y;
    });

    // =========================
    // html 생성
    // =========================
    let html = "";

    for (const item of data) {

        const id = item.id;

        const checked =
            state.selectedItems.has(id);

        const hold =
            cleanText(item.홀딩);

        const isFreeze =
            cleanText(item.동결) !== "";

        const isBlocked =
            cleanText(item.사용불가) !== "";

        const isHolding =
            hold !== "";

        let rowClass = "";

        if (checked)
            rowClass += " selected-row";

        if (isBlocked) {

            rowClass += " unuse-row";

        } else if (isFreeze) {

            rowClass += " freezed-row";

        } else if (isHolding) {

            rowClass += " holding-row";
        }

        if (state.flashIds.has(id)) {
            rowClass += " flash-row";
        }

        html += `
            <tr class="${rowClass}">

                <td>
                    <input
                        type="checkbox"
                        class="row-check"
                        data-id="${id}"
                        ${checked ? "checked" : ""}
                    >
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

            </tr>
        `;
    }

    // =========================
    // render
    // =========================
    dom.listDiv.innerHTML = html;

    // =========================
    // 총합
    // =========================
    const totalWeight =
        data.reduce((sum, item) => {

            return sum +
                (Number(item.재고) || 0);

        }, 0);

    const mean =
        data.reduce((sum, item) => {

            return sum +
                (Number(item.평중) || 0);

        }, 0);

    renderTableSize(
        data.length,
        totalWeight,
        mean
    );
}