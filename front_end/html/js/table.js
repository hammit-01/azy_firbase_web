import { state } from "./state.js";
import { dom } from "./dom.js";

const WH_CLASS = {
    "곤지암": "wh-곤지암",
    "곤CS":   "wh-곤CS",
    "곤SWC":  "wh-곤SWC",
    "곤대재":  "wh-곤대재",
    "곤대청":  "wh-곤대청",
    "곤삼진2": "wh-곤삼진2",
    "곤에이스처인": "wh-곤에이스처인",
};

function dueDateTag(dateStr) {
    const v = safeValue(dateStr);
    if (!v) return "";

    const due = new Date(v);
    if (isNaN(due.getTime())) return v;

    const limit = new Date();
    limit.setMonth(limit.getMonth() + 6);

    if (due <= limit) {
        return `<span class="due-tag-urgent">${v}</span>`;
    }
    return `<span class="due-tag-normal">${v}</span>`;
}

function whTag(warehouse) {
    const v = String(warehouse ?? "").trim();
    if (!v || v === "nan") return "";
    const cls = WH_CLASS[v] ?? "wh-default";
    return `<span class="wh-tag ${cls}">${v}</span>`;
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
// 모바일 카드 뷰
// =========================
function renderMobileView(data) {
    const el = document.getElementById("mobile-list");
    if (!el || window.innerWidth > 768) return; // 데스크톱은 스킵

    if (data.length === 0) {
        el.innerHTML = `<p class="mobile-empty">검색된 데이터가 없습니다</p>`;
        return;
    }

    let html = "";
    for (const item of data) {
        const id = item.id;
        const checked = state.selectedItems.has(id);
        const cls = WH_CLASS[String(item.창고 ?? "").trim()] ?? "wh-default";

        let cardCls = "mobile-card";
        if (checked)              cardCls += " mobile-selected";
        if (state.flashIds.has(id)) cardCls += " flash-row";
        if (item.상태 === "holding") cardCls += " mobile-holding";
        if (item.상태 === "freeze")  cardCls += " mobile-freeze";
        if (item.상태 === "stopped") cardCls += " mobile-stopped";
        if (item.상태 === "moving")  cardCls += " mobile-moving";

        const wh   = safeValue(item.창고);
        const name = safeValue(item.상품명);
        const qty  = safeValue(item.재고);

        html += `
        <div class="${cardCls}" data-id="${id}">
            <div class="mc-header">
                <input type="checkbox" class="row-check" data-id="${id}" ${checked ? "checked" : ""}>
                <span class="mc-name">${name}</span>
                ${wh ? `<span class="wh-tag ${cls}">${wh}</span>` : ""}
            </div>
            <div class="mc-tags">
                ${safeValue(item.브랜드) ? `<span class="s-tag">${safeValue(item.브랜드)}</span>` : ""}
                ${safeValue(item.등급)   ? `<span class="s-tag">${safeValue(item.등급)}</span>`   : ""}
                ${safeValue(item.ESTNO)  ? `<span class="s-tag">${safeValue(item.ESTNO)}</span>`  : ""}
                ${qty ? `<span class="s-tag s-tag-qty">${qty}박스</span>` : ""}
            </div>
            <div class="mc-info">
                <div class="mc-row"><span class="mc-label">유통기한</span>${dueDateTag(item.유통기한)}</div>
                <div class="mc-row"><span class="mc-label">평중</span>${safeValue(item.평중)}</div>
                ${safeValue(item.BL)     ? `<div class="mc-row mc-full"><span class="mc-label">BL</span>${safeValue(item.BL)}</div>` : ""}
                ${safeValue(item.출고일) ? `<div class="mc-row"><span class="mc-label">출고일</span>${safeValue(item.출고일)}</div>` : ""}
                ${safeValue(item.홀딩)   ? `<div class="mc-row mc-full"><span class="mc-label">홀딩</span>${safeValue(item.홀딩)}</div>` : ""}
                ${safeValue(item.메모)   ? `<div class="mc-row mc-full"><span class="mc-label">메모</span>${safeValue(item.메모)}</div>` : ""}
            </div>
        </div>`;
    }
    el.innerHTML = html;
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

    const field = "전체";

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

    const warehouse =
        document.querySelector(".show-warehouse").value;
    const brand =
        document.querySelector(".show-brand").value;
    const dataState =
        document.querySelector(".show-state").value;

    if (warehouse && warehouse !== "non") {
        data = data.filter(item => item.창고 === warehouse);
    }
    
    if (brand && brand !== "non") {
        data = data.filter(item => item.브랜드 === brand);
    }
    
    if (dataState && dataState !== "non") {
        data = data.filter(item => item.상태 === dataState);
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

    // 현재 표시 중인 행 저장 (전체 선택에 사용)
    state.filteredData = data;

    renderMobileView(data);

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

        const isHolding =
            hold !== "";

        let rowClass = "";

        if (checked)
            rowClass += " selected-row";

        if (isHolding)
            rowClass += " holding-row";

        if (state.flashIds.has(id))
            rowClass += " flash-row";

        if (item.상태 === "holding") rowClass += " holding-row";
        if (item.상태 === "freeze")  rowClass += " freezed-row";
        if (item.상태 === "stopped") rowClass += " stopped-row";
        if (item.상태 === "moving")  rowClass += " moving-row";

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
                <td>${whTag(item.창고)}</td>
                <td>${dueDateTag(item.유통기한)}</td>
                <td>${safeValue(item.평중)}</td>
                <td>${safeValue(item.출고일)}</td>
                <td>
                    ${safeValue(item.홀딩)}
                    ${item.상태 === "holding"
                        ? `<button class="complete-holding-btn" data-id="${id}" data-record-id="${item.holdingRecordId || ""}">✓ 완료</button>`
                        : ""}
                </td>
                <td>${safeValue(item.메모)}</td>
            </tr>
        `;

    }

    // =========================
    // render
    // =========================
    if (data.length === 0) {
        html = `
            <tr>
                <td colspan="13" style="text-align:center; padding:40px; color:#9ca3af; font-size:15px;">
                    검색된 데이터가 없습니다
                </td>
            </tr>
        `;
    }

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


