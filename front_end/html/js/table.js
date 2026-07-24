import { state } from "./state.js";
import { dom } from "./dom.js";
import { employeeSelect, stateSelect } from "./panel.js";
import { getStoredUser } from "./login.js";

const WH_CLASS = {
    "곤지암": "wh-곤지암",
    "곤CS":   "wh-곤CS",
    "곤SWC":  "wh-곤SWC",
    "곤대재":  "wh-곤대재",
    "곤대청":  "wh-곤대청",
    "곤삼진2": "wh-곤삼진2",
    "곤에이스처인": "wh-곤에이스처인",
};

function dueDateTag(dateStr, limitDate) {
    const v = safeValue(dateStr);
    if (!v) return "";

    const due = new Date(v);
    if (isNaN(due.getTime())) return v;

    if (due <= limitDate) {
        return `<span class="due-tag-urgent">${v}</span>`;
    }
    return `<span class="due-tag-normal">${v}</span>`;
}

const STATUS_BADGE = {
    holding: ["홀딩", "badge-holding"],
    freeze:  ["동결", "badge-freeze"],
    stopped: ["사용불가", "badge-stopped"],
    moving:  ["이고", "badge-moving"],
};

function statusBadge(state) {
    const entry = STATUS_BADGE[state];
    if (!entry) return "";
    return `<span class="mc-status-badge ${entry[1]}">${entry[0]}</span>`;
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

    const limitDate = new Date();
    limitDate.setMonth(limitDate.getMonth() + 6);

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
                ${statusBadge(item.상태)}
                ${wh ? `<span class="wh-tag ${cls}">${wh}</span>` : ""}
            </div>
            <div class="mc-tags">
                ${safeValue(item.브랜드) ? `<span class="s-tag">${safeValue(item.브랜드)}</span>` : ""}
                ${safeValue(item.등급)   ? `<span class="s-tag">${safeValue(item.등급)}</span>`   : ""}
                ${safeValue(item.ESTNO)  ? `<span class="s-tag">${safeValue(item.ESTNO)}</span>`  : ""}
            </div>
            <div class="mc-hero">
                <div class="mc-qty">${qty || 0}<span class="mc-qty-unit">박스</span></div>
                ${dueDateTag(item.유통기한, limitDate)}
            </div>
            <div class="mc-info">
                ${safeValue(item.평중)   ? `<div class="mc-row"><span class="mc-label">평중</span>${safeValue(item.평중)}</div>` : ""}
                ${safeValue(item.BL)     ? `<div class="mc-row mc-full"><span class="mc-label">BL</span>${safeValue(item.BL)}</div>` : ""}
                ${safeValue(item.출고일) ? `<div class="mc-row"><span class="mc-label">출고일</span>${safeValue(item.출고일)}</div>` : ""}
                ${safeValue(item.홀딩)   ? `<div class="mc-row mc-full"><span class="mc-label">홀딩</span>${safeValue(item.홀딩)}</div>` : ""}
                ${safeValue(item.메모)   ? `<div class="mc-row mc-full"><span class="mc-label">비고</span>${safeValue(item.메모)}</div>` : ""}
            </div>
        </div>`;
    }
    el.innerHTML = html;
}

// =========================
// 행 내 인라인 수정 / 홀딩 입력행
// =========================

// 저장된 유통기한은 "2028.01.04" 형식(점 구분) — <input type="date">는 "YYYY-MM-DD"만 인식하므로 변환
function toDateInputValue(v) {
    const s = safeValue(v);
    return s ? s.replace(/\./g, "-") : "";
}

function createUpdateRow(item) {
    const id = item.id;
    return `
        <tr class="update-row-edit" data-id="${id}">
            <td><input type="checkbox" class="row-check" data-id="${id}" checked></td>
            <td data-label="상품명"><input type="text" class="update-name cell-input" data-id="${id}" value="${safeValue(item.상품명)}"></td>
            <td data-label="브랜드"><input type="text" class="update-brand cell-input" data-id="${id}" value="${safeValue(item.브랜드)}"></td>
            <td data-label="등급"><input type="text" class="update-grade cell-input" data-id="${id}" value="${safeValue(item.등급)}"></td>
            <td data-label="ESTNO"><input type="text" class="update-estNo cell-input" data-id="${id}" value="${safeValue(item.ESTNO)}"></td>
            <td data-label="재고"><input type="number" class="update-qty cell-input" data-id="${id}" value="${safeValue(item.재고)}"></td>
            <td data-label="BL"><input type="text" class="update-bl cell-input" data-id="${id}" value="${safeValue(item.BL)}"></td>
            <td data-label="창고"><input type="text" class="update-warehouse cell-input" data-id="${id}" value="${safeValue(item.창고)}"></td>
            <td data-label="유통기한"><input type="date" class="update-dueDate cell-input" data-id="${id}" value="${toDateInputValue(item.유통기한)}"></td>
            <td data-label="평중"><input type="number" step="0.01" class="update-weight cell-input" data-id="${id}" value="${safeValue(item.평중)}"></td>
            <td data-label="비고">
                <div class="insert-row-memo-cell">
                    <input type="text" class="update-memo cell-input" data-id="${id}" value="${safeValue(item.메모)}" placeholder="비고">
                    ${stateSelect("update-state", safeValue(item.상태) || "없음", id)}
                    <button class="select-update-btn" data-id="${id}" title="저장">✓</button>
                    <button class="select-delete-btn" data-id="${id}" title="삭제">🗑</button>
                    <button class="cancel-btn" data-id="${id}" title="취소">✕</button>
                </div>
                <input type="hidden" class="update-releaseDate" data-id="${id}" value="${safeValue(item.출고일)}">
                <input type="hidden" class="update-holding" data-id="${id}" value="${safeValue(item.홀딩)}">
            </td>
        </tr>
    `;
}

// 홀딩 대상 행 밑에 붙는 입력행 — 홀딩수량/평균중량/출고일자/담당자/비고만 입력, 나머지는 원본 행에서 그대로 가져감
function createHoldingInsertRow(item) {
    const id = item.id;
    const user = getStoredUser();
    // 사원은 자기 이름으로 자동 고정, 담당자 선택 UI 자체를 안 보여줌 (편집자는 기존처럼 선택 가능)
    const assigneeField = user?.권한 === "사원"
        ? `<input type="hidden" class="hold-note" data-id="${id}" value="${user.이름}">`
        : employeeSelect("hold-note", id, "");
    return `
        <tr class="holding-insert-row" data-id="${id}">
            <td></td>
            <td class="holding-inherited" data-label="상품명">${safeValue(item.상품명)}</td>
            <td class="holding-inherited" data-label="브랜드">${safeValue(item.브랜드)}</td>
            <td class="holding-inherited" data-label="등급">${safeValue(item.등급)}</td>
            <td class="holding-inherited" data-label="ESTNO">${safeValue(item.ESTNO)}</td>
            <td data-label="수량"><input type="number" class="hold-qty cell-input" data-id="${id}" placeholder="수량"></td>
            <td class="holding-inherited" data-label="BL">${safeValue(item.BL)}</td>
            <td data-label="담당자 · 출고일자">
                <div class="hold-stack">
                    ${assigneeField}
                    <input type="date" class="hold-releaseDate cell-input" data-id="${id}" title="출고일자">
                </div>
            </td>
            <td class="holding-inherited" data-label="유통기한">${safeValue(item.유통기한)}</td>
            <td data-label="평중"><input type="number" step="0.01" class="hold-weight cell-input" data-id="${id}" value="${safeValue(item.평중)}"></td>
            <td data-label="비고">
                <div class="insert-row-memo-cell">
                    <input type="text" class="hold-memo cell-input" data-id="${id}" placeholder="비고">
                    <button class="select-holding-btn" data-id="${id}" title="저장">✓</button>
                    <button class="cancel-btn" data-id="${id}" title="취소">✕</button>
                </div>
            </td>
        </tr>
    `;
}

// =========================
// 우하단 전체 처리 바 — 추가/수정/홀딩 입력행이 있을 때만 표시
// =========================
export function renderBulkActionBar() {
    const bar = document.getElementById("bulk-action-bar");
    if (!bar) return;

    const insertCount = document.querySelectorAll("tr.insert-card").length;
    const updateCount = document.querySelectorAll("tr.update-row-edit").length;
    const holdingCount = document.querySelectorAll("tr.holding-insert-row").length;

    let cls = "", label = "", btnLabel = "", btnCls = "";
    if (insertCount > 0) {
        cls = "bulk-insert"; label = `${insertCount}개 상품 입력 중`; btnLabel = "전체 추가"; btnCls = "all-insert-btn";
    } else if (updateCount > 0) {
        cls = "bulk-update"; label = `${updateCount}개 항목 수정 중`; btnLabel = "전체 수정"; btnCls = "all-update-btn";
    } else if (holdingCount > 0) {
        cls = "bulk-holding"; label = `${holdingCount}개 항목 홀딩 입력 중`; btnLabel = "전체 홀딩"; btnCls = "all-holding-btn";
    }

    if (!cls) {
        bar.classList.remove("visible");
        return;
    }

    bar.innerHTML = `
        <div class="bulk-action-card ${cls}">
            <span class="bulk-action-label">${label}</span>
            <button class="${btnCls}">${btnLabel}</button>
        </div>
    `;
    bar.classList.add("visible");
}

// =========================
// 창고 필터 옵션 — 현재 크롤링된(=실제 데이터에 존재하는) 창고만 가나다순으로
// =========================
export function renderWarehouseOptions() {
    const select = document.querySelector(".show-warehouse");
    if (!select) return;

    const current = select.value;

    const warehouses = [...new Set(
        state.allData.map(item => String(item.창고 ?? "").trim()).filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, "ko"));

    select.innerHTML =
        `<option value="">창고</option>` +
        warehouses.map(w => `<option value="${w}">${w}</option>`).join("");

    if (warehouses.includes(current)) select.value = current;
}

// =========================
// 정렬 헤더 인디케이터
// =========================
const SORT_LABELS = {
    "상품명": "상품명", "브랜드": "브랜드", "등급": "등급",
    "ESTNO": "ESTNO", "재고": "재고", "BL": "BL",
    "창고": "창고", "유통기한": "유통기한", "평중": "평균", "메모": "비고"
};

export function updateSortHeaders() {
    Object.keys(SORT_LABELS).forEach(key => {
        const th = document.querySelector(`th[data-key="${key}"]`);
        if (!th) return;
        const entry = state.sortColumns.find(s => s.key === key);
        const arrow = entry ? (entry.dir === 1 ? " ▲" : " ▼") : "";
        th.textContent = SORT_LABELS[key] + arrow;
        th.classList.toggle("sort-active", !!entry);
    });
}

// =========================
// 테이블 사이즈
// =========================
export function renderTableSize(count, size, mean) {

    const container =
        document.querySelector(".table_size");

    if (!container) return;

    // 요소를 처음 한 번만 만들고 이후엔 텍스트만 갱신 — .selection-summary가 매 렌더마다
    // 지워졌다 새로 생기면 선택 배지 상태가 유지되지 않기 때문
    let mainEl = container.querySelector(".table_size_main");
    if (!mainEl) {
        container.innerHTML = `
            <div class="table_size_main"></div>
            <div class="table_size_weight"></div>
            <div class="selection-summary"></div>
            <span class="table_size_updated"></span>
        `;
        mainEl = container.querySelector(".table_size_main");
    }
    const weightEl = container.querySelector(".table_size_weight");
    const updatedEl = container.querySelector(".table_size_updated");

    const timestamps = state.allData
        .map(item => item.updated_at)
        .filter(Boolean)
        .map(t => new Date(t))
        .filter(d => !isNaN(d.getTime()));

    let lastUpdatedText = "";
    if (timestamps.length) {
        const latest = new Date(Math.max(...timestamps));
        const pad = n => String(n).padStart(2, "0");
        lastUpdatedText = `${latest.getFullYear()}-${pad(latest.getMonth() + 1)}-${pad(latest.getDate())} ${pad(latest.getHours())}:${pad(latest.getMinutes())} 기준`;
    }

    mainEl.textContent = `총 ${count} 행 / 총 ${size} 박스`;
    weightEl.textContent = `총 중량 ${mean.toFixed(2)} KG`;
    updatedEl.textContent = lastUpdatedText;
    updatedEl.style.display = lastUpdatedText ? "" : "none";
}

// =========================
// 테이블 렌더
// =========================
export function renderTable() {

    if (!dom.searchInput) return;

    const limitDate = new Date();
    limitDate.setMonth(limitDate.getMonth() + 6);

    let data = [...state.allData];

    const keyword =
        cleanText(
            dom.searchInput.value
        ).toLowerCase();

    const keyword2 =
        cleanText(
            dom.searchInput2?.value || ""
        ).toLowerCase();

    // =========================
    // 검색 필터 (검색1 · 검색2 둘 다 만족해야 함 — AND)
    // =========================
    // id/pk 등 내부 식별자는 생성 당시 상품명이 그대로 박혀있어서(수정해도 안 바뀜)
    // 검색 대상에 포함하면 이미 이름 바꾼 상품이 옛날 이름으로도 검색되는 문제가 생김 —
    // 화면에 실제로 보이는 컬럼만 검색 대상으로 한정
    const SEARCHABLE_KEYS = [
        "상품명", "브랜드", "등급", "ESTNO", "재고", "BL", "창고",
        "유통기한", "중량", "평중", "출고일", "홀딩", "상태", "메모"
    ];

    const matchesKeyword = (item, kw) =>
        SEARCHABLE_KEYS.some(key => {
            const value = item[key];

            if (value == null)
                return false;

            return cleanText(value)
                .toLowerCase()
                .includes(kw);
        });

    if (keyword) {
        data = data.filter(item => matchesKeyword(item, keyword));
    }

    if (keyword2) {
        data = data.filter(item => matchesKeyword(item, keyword2));
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

    // 박스 합계는 빈 상품 제거 전 기준으로 계산
    const dataForTotal = data;

    // =========================
    // 빈 상품 제거 (화면 표시 전용)
    // =========================
    data = data.filter(item => {

        return cleanText(item.상품명) !== "";
    });

    // =========================
    // 정렬
    // =========================
    if (state.sortColumns.length > 0) {
        data.sort((a, b) => {
            for (const { key, dir } of state.sortColumns) {
                const factor = dir === 1 ? 1 : -1;
                const av = String(a[key] ?? "").trim();
                const bv = String(b[key] ?? "").trim();
                if (!av && !bv) continue;
                if (!av) return 1;
                if (!bv) return -1;
                if (key === "재고" || key === "평중") {
                    const an = Number(av), bn = Number(bv);
                    if (!isNaN(an) && !isNaN(bn)) {
                        const r = (an - bn) * factor;
                        if (r !== 0) return r;
                        continue;
                    }
                }
                if (av < bv) return -factor;
                if (av > bv) return factor;
            }
            return 0;
        });
    } else {
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
    }

    // 헤더 인디케이터 동기화
    updateSortHeaders();

    // 현재 표시 중인 행 저장 (전체 선택에 사용)
    state.filteredData = data;

    renderMobileView(data);

    // =========================
    // html 생성
    // =========================
    let html = "";

    // 재렌더링 중에도 입력 중이던 인라인 수정/홀딩 행은 값 보존을 위해 재사용
    const existingUpdateRows = {};
    const existingHoldingRows = {};
    document.querySelectorAll("tr.update-row-edit[data-id]").forEach(tr => {
        existingUpdateRows[tr.dataset.id] = tr.outerHTML;
    });
    document.querySelectorAll("tr.holding-insert-row[data-id]").forEach(tr => {
        existingHoldingRows[tr.dataset.id] = tr.outerHTML;
    });

    for (const item of data) {

        const id = item.id;

        const checked =
            state.selectedItems.has(id);

        if (state.crudData === "update" && checked) {
            html += existingUpdateRows[id] || createUpdateRow(item);
            continue;
        }

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
            <tr class="${rowClass}" data-id="${id}" data-출고일="${safeValue(item.출고일)}" data-홀딩="${safeValue(item.홀딩)}">

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
                <td>${dueDateTag(item.유통기한, limitDate)}</td>
                <td>${safeValue(item.평중)}</td>
                <td>${safeValue(item.메모)}</td>
            </tr>
        `;

        if (state.crudData === "holding" && checked) {
            html += existingHoldingRows[id] || createHoldingInsertRow(item);
        }

    }

    // =========================
    // render
    // =========================
    if (data.length === 0) {
        html = `
            <tr>
                <td colspan="12" style="text-align:center; padding:40px; color:#9ca3af; font-size:15px;">
                    검색된 데이터가 없습니다
                </td>
            </tr>
        `;
    }

    dom.listDiv.innerHTML = html;

    // =========================
    // 총합 (빈 상품명 포함 전체 기준)
    // =========================
    const totalWeight =
        dataForTotal.reduce((sum, item) => {

            return sum +
                (Number(item.재고) || 0);

        }, 0);

    const mean =
        dataForTotal.reduce((sum, item) => {

            return sum +
                (Number(item.평중) || 0);

        }, 0);

    renderTableSize(
        dataForTotal.length,
        totalWeight,
        mean
    );
}


