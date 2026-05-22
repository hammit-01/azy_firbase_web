import { state } from "./state.js";
import { dom } from "./dom.js";
import { getItems } from "./firestoreService.js";

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
// 테이블 사이즈
// =========================
export function renderTableSize(count, size, mean) {

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
    const sortOrder = [
        "상품명",
        "브랜드",
        "등급",
        "ESTNO",
        "창고",
        "BL",
        "재고",
    ];

    data.sort((a, b) => {

        for (const key of sortOrder) {

            let av = String(a[key] ?? "").trim();
            let bv = String(b[key] ?? "").trim();

            // =========================
            // 영어로 시작하면 맨 뒤
            // =========================
            const aEng = /^[A-Za-z]/.test(av);
            const bEng = /^[A-Za-z]/.test(bv);

            if (aEng && !bEng) return 1;
            if (!aEng && bEng) return -1;

            // 숫자 비교
            const an = Number(av);
            const bn = Number(bv);

            if (!isNaN(an) && !isNaN(bn)) {
                av = an;
                bv = bn;
            }

            // 오름차순
            if (av < bv) return -1;
            if (av > bv) return 1;
        }

        return 0;
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


