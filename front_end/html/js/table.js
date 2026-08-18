import { state } from "./state.js";
import { dom } from "./dom.js";
import { employeeSelect, stateSelect } from "./panel.js";
import { getStoredUser, hasEditorAccess } from "./login.js";
import { getAllReservations, getAllOutbound } from "./firestoreService.js";

// 영문 브랜드를 한글 표기로 쳐도 검색되게 하는 별칭 테이블(2026-08-14).
// key: 한글 표기, value: 실제 데이터의 영문 브랜드값 — 데이터에 실제로 존재하는
// 브랜드 기준으로 만들었음. 새 브랜드 생기면 여기 추가.
const BRAND_ALIASES = {
    "파이브스타": "5 STAR", "오스타": "5 STAR", "파이브": "5 STAR",
    "에이씨씨": "ACC", "에씨씨": "ACC",
    "아프코": "AFFCO",
    "에이에프지": "AFG", "에이에프쥐": "AFG",
    "아그로수퍼": "AGROSUPER", "아그로": "AGROSUPER",
    "알레한드로": "ALEJANDRO", "알레한": "ALEJANDRO",
    "에이엠지": "AMG",
    "에이엠에이치": "AMH",
    "에이엠피": "AMP",
    "오로라": "AURORA", "오로": "AURORA",
    "빈다리": "BINDAREE",
    "카지노": "CASINO",
    "셀라": "CELRA",
    "크릭스톤": "CREEKSTONE", "크릭": "CREEKSTONE",
    "엑셀": "EXCEL", "액셀": "EXCEL",
    "그린리": "GREENLEA",
    "하비": "HARVEY",
    "하이마운틴": "HIGH MOUNTAIN", "마운틴": "HIGH MOUNTAIN",
    "하이라이프": "HYLIFE", "라이프": "HYLIFE",
    "아이비피": "IBP",
    "아이씨피": "ICP",
    "아이에프티": "IFT",
    "인카를롭사": "INCARLOPSA", "잉카롭사": "INCARLOPSA", "잉카": "INCARLOPSA",
    "케켄": "KEKEN",
    "킬코이": "KILCOY",
    "리테라": "LITERA",
    "락스": "LOCKS", "록스": "LOCKS", "럭스": "LOCKS",
    "엔비피": "NBP", "앤비피": "NBP",
    "오키": "OAKEY",
    "올리멜": "OLYMEL", "올리맬": "OLYMEL",
    "오마하": "OMAHA",
    "파itel": "PATEL", "바텔": "PATEL",
    "페르디가오": "PERDIGAO", "페르디": "PERDIGAO",
    "피피씨에스": "PPCS","피피씨": "PPCS",
    "프로안": "PROAN",
    "리바삼": "RIVASAM", "리바쌈": "RIVASAM",
    "로스데라": "ROSDERRA", "로즈데라": "ROSDERRA",
    "루돌프": "RUDOLF",
    "사디아": "SADIA",
    "세아라": "SEARA", "씨에라": "SEARA", "시에라": "SEARA",
    "스미스필드": "SMITHFIELD", "스미스": "SMITHFIELD",
    "에스티엑스": "STX",
    "수카르네": "SUKARNE",
    "스위프트": "SWIFT",
    "테이즈": "TEYS", "티스": "TEYS",
    "토마스": "THOMAS",
    "티칸": "TICAN",
    "토니스": "TONNIES", "퇴니스": "TONNIES", "퇴니시": "TONNIES",
    "비브라": "VIBRA",
    "홀스톤": "WHOLESTONE",
    "윙햄": "WINGHAM",
};

// 타창고매출현황(sales.html) "등록완료" 체크박스 — mysql outbound.등록 열이 이
// 창고들만 의미가 있어서(2026-08-18) 그 외 창고는 체크박스 없이 빈칸.
const REGISTER_REQUIRED_WAREHOUSES = new Set(["신우냉장", "CS"]);

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
    holding: ["예약", "badge-holding"],
    freeze:  ["동결", "badge-freeze"],
    stopped: ["사용불가", "badge-stopped"],
    moving:  ["이고", "badge-moving"],
};

function statusBadge(state) {
    const entry = STATUS_BADGE[state];
    if (!entry) return "";
    return `<span class="mc-status-badge ${entry[1]}">${entry[0]}</span>`;
}

// 가용재고 — 예약이 실재고보다 많아져 0 이하가 되면(수동 재고 조정 등으로 드물게 발생)
// 빨간 배지로 눈에 띄게 표시. 이고 취합 행 등 이 값 자체가 없는 행은 빈칸.
function availableCell(value) {
    if (value === undefined || value === null || value === "") return "";
    const n = Number(value);
    if (isNaN(n)) return "";
    if (n <= 0) return `<span class="due-tag-urgent">${n}</span>`;
    return String(n);
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
        if (item._isMoving)          cardCls += " mobile-moving-inventory";

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
                ${Number(item.예약수량) > 0 ? `<div class="mc-row"><span class="mc-label">예약</span>${safeValue(item.예약수량)}</div>` : ""}
                ${Number(item.예약수량) > 0 ? `<div class="mc-row"><span class="mc-label">가용</span>${availableCell(item.가용재고)}</div>` : ""}
                ${safeValue(item.평중)   ? `<div class="mc-row"><span class="mc-label">평중</span>${safeValue(item.평중)}</div>` : ""}
                ${safeValue(item.BL)     ? `<div class="mc-row mc-full"><span class="mc-label">BL</span>${safeValue(item.BL)}</div>` : ""}
                ${safeValue(item.출고일) ? `<div class="mc-row"><span class="mc-label">출고일</span>${safeValue(item.출고일)}</div>` : ""}
                ${safeValue(item.홀딩)   ? `<div class="mc-row mc-full"><span class="mc-label">예약자</span>${safeValue(item.홀딩)}</div>` : ""}
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
            <td data-label="BL"><input type="text" class="update-bl cell-input" data-id="${id}" value="${safeValue(item.BL)}"></td>
            <td data-label="창고"><input type="text" class="update-warehouse cell-input" data-id="${id}" value="${safeValue(item.창고)}"></td>
            <td data-label="재고"><input type="number" class="update-qty cell-input" data-id="${id}" value="${safeValue(item.재고)}"></td>
            <td class="holding-inherited" data-label="예약">${Number(item.예약수량) > 0 ? safeValue(item.예약수량) : ""}</td>
            <td class="holding-inherited" data-label="가용">${availableCell(item.가용재고)}</td>
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
            <td class="holding-inherited" data-label="BL">${safeValue(item.BL)}</td>
            <td data-label="담당자 · 출고일자">
                <div class="hold-stack">
                    ${assigneeField}
                    <input type="date" class="hold-releaseDate cell-input" data-id="${id}" title="출고일자">
                </div>
            </td>
            <td data-label="수량"><input type="number" class="hold-qty cell-input" data-id="${id}" placeholder="수량"></td>
            <td class="holding-inherited" data-label="예약">${Number(item.예약수량) > 0 ? safeValue(item.예약수량) : ""}</td>
            <td class="holding-inherited" data-label="가용">${availableCell(item.가용재고)}</td>
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
        cls = "bulk-holding"; label = `${holdingCount}개 항목 예약 입력 중`; btnLabel = "전체 예약"; btnCls = "all-holding-btn";
    }

    if (!cls) {
        // innerHTML을 비워야 카드가 DOM에서 사라져 차지하던 자리도 없어짐 —
        // visible 클래스만 떼면 opacity/transform으로 안 보이기만 하고 레이아웃
        // 공간은 그대로 남아있었음(2026-08-06 발견).
        bar.classList.remove("visible");
        bar.innerHTML = "";
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
// 브랜드 필터 옵션 — 창고와 동일한 방식: 고정 목록 대신 현재 데이터에 실제로
// 존재하는 브랜드만 가나다순으로(2026-08-06 — 하드코딩 목록이라 새 브랜드가
// 추가돼도 필터에 안 나타나던 문제 수정)
// =========================
export function renderBrandOptions() {
    const select = document.querySelector(".show-brand");
    if (!select) return;

    const current = select.value;

    const brands = [...new Set(
        state.allData.map(item => String(item.브랜드 ?? "").trim()).filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, "ko"));

    select.innerHTML =
        `<option value="">브랜드</option>` +
        brands.map(b => `<option value="${b}">${b}</option>`).join("");

    if (brands.includes(current)) select.value = current;
}

// =========================
// 상품명 필터 옵션 — 창고/브랜드와 동일한 방식(2026-08-06)
// =========================
export function renderProductNameOptions() {
    const select = document.querySelector(".show-product-name");
    if (!select) return;

    const current = select.value;

    const names = [...new Set(
        state.allData.map(item => String(item.상품명 ?? "").trim()).filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, "ko"));

    select.innerHTML =
        `<option value="">상품명</option>` +
        names.map(n => `<option value="${n}">${n}</option>`).join("");

    if (names.includes(current)) select.value = current;
}

// =========================
// 정렬 헤더 인디케이터
// =========================
const SORT_LABELS = {
    "상품명": "상품명", "브랜드": "브랜드", "등급": "등급",
    "ESTNO": "ESTNO", "재고": "재고", "예약수량": "예약", "가용재고": "가용", "BL": "BL",
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
            <div class="table_size_top">
                <div class="table_size_main"></div>
                <div class="selection-summary"></div>
            </div>
            <div class="table_size_weight"></div>
        `;
        mainEl = container.querySelector(".table_size_main");
    }
    const weightEl = container.querySelector(".table_size_weight");
    // 로그인 박스 밑에 고정 배치된 엘리먼트 — .table_size 컨테이너 밖에 있어 전역 조회
    const updatedEl = document.querySelector(".table_size_updated");

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
// 예약 목록 (예약수량 클릭 시 아코디언으로 펼쳐서 보여줌 — 조회 전용, 취소는 안 됨)
// =========================
export function createReservationListRow(pk, reservations) {
    if (!reservations || reservations.length === 0) {
        return `<tr class="reservation-list-row"><td colspan="13">예약 내역이 없습니다</td></tr>`;
    }
    const items = reservations.map(r => `
        <span class="reservation-list-item">
            ${safeValue(r.메모) || "(거래처 미입력)"} · ${safeValue(r.수량)}박스${safeValue(r.홀딩) ? ` · ${safeValue(r.홀딩)}` : ""}
        </span>
    `).join("");
    return `<tr class="reservation-list-row" data-pk="${pk}"><td colspan="13">${items}</td></tr>`;
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

            const text = cleanText(value).toLowerCase();
            if (text.includes(kw)) return true;

            // 한글 표기 검색(예: "엑셀" 입력 -> 브랜드 "EXCEL" 매칭, 2026-08-14) —
            // 입력한 키워드가 별칭 테이블의 한글 표기 일부고, 그 별칭이 가리키는
            // 영문값이 이 필드값과 같으면 매치로 본다.
            return Object.entries(BRAND_ALIASES).some(([ko, en]) =>
                ko.includes(kw) && text === en.toLowerCase()
            );
        });

    if (keyword) {
        data = data.filter(item => matchesKeyword(item, keyword));
    }

    if (keyword2) {
        data = data.filter(item => matchesKeyword(item, keyword2));
    }

    const warehouse =
        document.querySelector(".show-warehouse").value;
    const productName =
        document.querySelector(".show-product-name")?.value || "";
    const brand =
        document.querySelector(".show-brand").value;
    const dataState =
        document.querySelector(".show-state").value;

    if (warehouse && warehouse !== "non") {
        data = data.filter(item => item.창고 === warehouse);
    }

    if (productName && productName !== "non") {
        data = data.filter(item => item.상품명 === productName);
    }

    if (brand && brand !== "non") {
        data = data.filter(item => item.브랜드 === brand);
    }

    if (dataState && dataState !== "non") {
        // "예약"(value=holding)은 더 이상 상태 컬럼에 안 찍힘(예약이 실재고 행과 분리돼서
        // 별도 표시 행을 안 만듦) — 예약수량 > 0인 행을 보여주는 걸로 대체
        data = dataState === "holding"
            ? data.filter(item => Number(item.예약수량) > 0)
            : data.filter(item => item.상태 === dataState);
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
                if (key === "재고" || key === "평중" || key === "예약수량" || key === "가용재고") {
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
        if (item._isMoving)          rowClass += " moving-inventory-row";

        html += `
            <tr class="${rowClass}" data-id="${id}" data-출고일="${safeValue(item.출고일)}" data-홀딩="${safeValue(item.홀딩)}" data-pk="${item._rawId ?? id}" data-예약수량="${Number(item.예약수량) || 0}">

                <td>
                    <input
                        type="checkbox"
                        class="row-check"
                        data-id="${id}"
                        ${checked ? "checked" : ""}
                        ${item._isMoving ? "disabled title=\"이고 취합 시트 데이터 — 읽기 전용\"" : ""}
                    >
                </td>

                <td>${safeValue(item.상품명)}</td>
                <td>${safeValue(item.브랜드)}</td>
                <td>${safeValue(item.등급)}</td>
                <td>${safeValue(item.ESTNO)}</td>
                <td>${safeValue(item.BL)}</td>
                <td>${whTag(item.창고)}</td>
                <td>${safeValue(item.재고)}</td>
                <td>${Number(item.예약수량) > 0
                    ? `<button class="view-reservations-btn" data-pk="${item._rawId ?? id}">${safeValue(item.예약수량)}</button>`
                    : ""}</td>
                <td>${availableCell(item.가용재고)}</td>
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
                <td colspan="13" style="text-align:center; padding:40px; color:#9ca3af; font-size:15px;">
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

    renderChangesTab();
}

// =========================
// 업데이트(신규/갱신) 탭 — 어제 마감 스냅샷(state.yesterdayById)과 지금 데이터를
// 직접 비교해서 신규/변경된 행만 모아 보여줌. moving_inventory 행은 매 사이클
// 통째로 갈아끼우는 데이터라 "신규/갱신" 개념이 안 맞으므로 제외.
// =========================
const _COMPARE_FIELDS = ["상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "유통기한", "평중", "출고일", "재고", "메모"];

let _lastChangesRows = [];
export function getChangesTabRows() {
    return _lastChangesRows;
}

export function renderChangesTab() {
    const container = document.querySelector(".changes-container");
    const listEl = document.getElementById("changes-list");
    if (!container || !listEl || container.style.display === "none") return;

    const results = [];
    for (const item of state.allData) {
        if (item._isMoving) continue;
        if (item.상태 === "holding") continue; // 홀딩 중인 행은 신규/변경 집계에서 제외
        const prev = state.yesterdayById.get(`${item._source}:${item._rawId}`);
        if (!prev) {
            results.push({ item, prev: null, isNew: true, changedSet: new Set() });
            continue;
        }
        const changedSet = new Set(
            _COMPARE_FIELDS.filter(f => String(prev[f] ?? "") !== String(item[f] ?? ""))
        );
        if (changedSet.size > 0) {
            results.push({ item, prev, isNew: false, changedSet });
        }
    }

    // 신규 먼저, 그다음 상품명 가나다순
    results.sort((a, b) => (b.isNew - a.isNew) || String(a.item.상품명 ?? "").localeCompare(String(b.item.상품명 ?? ""), "ko"));

    // 다운로드 버튼에서 그대로 쓸 수 있게 지금 화면에 뜬 행을 저장해둠
    _lastChangesRows = results.map(({ item, prev, isNew }) => ({
        ...item,
        changed_fields: isNew ? "__NEW__" : "변경",
        _prevQty: prev ? prev.재고 : "",
    }));

    const cell = (changedSet, key, innerHtml) =>
        `<td class="${changedSet.has(key) ? "changes-cell-changed" : ""}">${innerHtml}</td>`;
    // 재고는 바뀐 경우 "이전값 → 현재값"으로 차이가 바로 보이게
    const qtyCell = ({ item, prev, changedSet }) => {
        if (changedSet.has("재고") && prev) {
            return `<td class="changes-cell-changed">${safeValue(prev.재고)} → ${safeValue(item.재고)}</td>`;
        }
        return cell(changedSet, "재고", safeValue(item.재고));
    };

    let html = `
        <div class="changes-count">
            어제 대비 신규/변경 ${results.length}건
            <button class="changes-download-btn">엑셀 다운로드</button>
        </div>
    `;
    html += `
        <table class="changes-table">
            <thead>
                <tr>
                    <th>구분</th><th>상품명</th><th>브랜드</th><th>등급</th><th>ESTNO</th>
                    <th>재고</th><th>BL</th><th>창고</th>
                </tr>
            </thead>
            <tbody>
                ${results.map(r => {
                    const { item, isNew, changedSet } = r;
                    const rowCls = isNew ? "changes-row-new" : "changes-row-updated";
                    return `
                        <tr class="${rowCls}">
                            <td>${isNew ? "신규" : "변경"}</td>
                            ${cell(changedSet, "상품명", safeValue(item.상품명))}
                            ${cell(changedSet, "브랜드", safeValue(item.브랜드))}
                            ${cell(changedSet, "등급", safeValue(item.등급))}
                            ${cell(changedSet, "ESTNO", safeValue(item.ESTNO))}
                            ${qtyCell(r)}
                            ${cell(changedSet, "BL", safeValue(item.BL))}
                            ${cell(changedSet, "창고", whTag(item.창고))}
                        </tr>
                    `;
                }).join("") || `
                    <tr><td colspan="8" style="text-align:center; padding:40px; color:#9ca3af;">어제 대비 변경 없음</td></tr>
                `}
            </tbody>
        </table>
    `;

    listEl.innerHTML = html;
}

// =========================
// 예약 현황 탭 — 편집자는 담당자별로 묶어서 전체를 보고, 사원은 자기 예약만 본다.
// =========================
// data-* 속성값 안에 큰따옴표가 있으면 마크업이 깨지므로 이스케이프
function attrEscape(v) {
    return String(v ?? "").replace(/"/g, "&quot;");
}

// 예약/출고 행의 "전달사항" 느낌표 버튼(2026-08-14) — 메시지 있으면 강조,
// 없으면 흐리게. 클릭하면 팝업(showNoteModal)에서 보기/수정.
function noteBtn(r, isSalesPage, canOthers = true) {
    if (isSalesPage && !canOthers) return "";
    const note = safeValue(r.전달사항);
    // 마우스 올리면 내용이 바로 보이게(2026-08-19) — 없으면 기존처럼 안내 문구
    const tooltip = note ? attrEscape(note) : "전달사항 추가";
    return `<button class="reservation-note-btn${note ? " has-note" : ""}" data-id="${r.id}" data-sales="${isSalesPage ? "1" : ""}" data-note="${attrEscape(r.전달사항)}" title="${tooltip}">!</button>`;
}

// 타창고매출현황 액션 권한(2026-08-18) — 편집자/관리자는 전부 가능, 그 외 사원은
// 자신이 담당자인 행의 "출고변경"만 가능(canEdit)하고 나머지 액션(출고완료/출고취소/
// 등록완료/전달사항)은 못 함(canOthers). 예약현황 탭은 애초에 본인 예약만 보여줘서
// (renderReservationsTab) 이 제한이 필요 없다 — isSalesPage일 때만 적용.
function salesAccess(r) {
    const user = getStoredUser();
    const isEditor = hasEditorAccess(user?.권한);
    const isOwner = !!user?.이름 && r.담당자 === user.이름;
    return { canEdit: isEditor || isOwner, canOthers: isEditor };
}

// sales.html "등록완료" 체크박스(2026-08-18) — 창고가 신우냉장/CS인 행만 노출,
// 체크되기 전엔 needsRegisterBlock()이 true가 되고 출고완료 버튼에
// data-needs-register="1"이 붙는다 — events.js가 그 상태에서 클릭을 가로채
// 팝업으로 안내한다(버튼을 disabled로 막으면 클릭해도 아무 반응이 없어
// 헷갈린다는 피드백으로 2026-08-18 변경).
function needsRegister(r) {
    return REGISTER_REQUIRED_WAREHOUSES.has(String(r.창고 ?? "").trim());
}
function registerCheckboxHtml(r, canOthers = true) {
    return needsRegister(r) && canOthers
        ? `<input type="checkbox" class="outbound-register-check" data-id="${r.id}" ${r.등록 ? "checked" : ""}>`
        : "";
}
function needsRegisterBlock(r) {
    return needsRegister(r) && !r.등록 && r.status !== "COMPLETED";
}

// sales.html 단가/중량 = 거래처 문자열에 "이름 가격원 중량kg" 형태로 같이 인코딩
// (2026-08-14). 예: "에이젯유통 111999원 22.5kg" -> prefix="에이젯유통",
// price=111999, weight=22.5. 거래처/단가/중량 모두 예약 테이블에 자체 컬럼이
// 없어서 이 문자열 하나에 다 담아 파싱/재조합한다.
export function clientPrefix(거래처) {
    const s = String(거래처 ?? "");
    const idx = s.indexOf(" ");
    return idx === -1 ? s : s.slice(0, idx);
}
export function parseUnitPrice(거래처) {
    const m = String(거래처 ?? "").match(/(\d[\d,]*)\s*원/);
    return m ? Number(m[1].replace(/,/g, "")) : null;
}
export function parseWeight(거래처) {
    const m = String(거래처 ?? "").match(/(\d+(?:\.\d+)?)\s*kg/i);
    return m ? Number(m[1]) : null;
}
export function formatUnitPrice(n) {
    return (n === null || n === undefined || n === "" || isNaN(n)) ? "" : Number(n).toLocaleString("ko-KR");
}
export function formatWeight(n) {
    return (n === null || n === undefined || n === "" || isNaN(n)) ? "" : String(Number(n));
}
// 수정 모달 저장 시 prefix + 새 단가/중량을 다시 거래처 문자열로 합침
export function buildClientWithDetails(prefix, price, weight) {
    let out = String(prefix ?? "").trim();
    if (price !== null && price !== undefined && price !== "") out += ` ${price}원`;
    if (weight !== null && weight !== undefined && weight !== "") out += ` ${weight}kg`;
    return out;
}

// 모바일 카드 뷰 — 데스크톱 .reservations-table과 같은 데이터를 카드로 보여줌
// (max-width:768px에서 CSS가 테이블 대신 이걸 노출 — 좁은 화면에서 표가 잘려
// 사용완료/홀딩취소 버튼에 손이 안 닿던 문제 수정)
// isSalesPage: sales.html에서는 "예약일"(홀딩일자) 대신 "단가"+"중량" 칸을 보여준다
// (2026-08-14). 단가/중량은 예약 데이터에 아직 없는 값이라 빈칸일 수 있다.
function reservationCardHtml(r, isSalesPage = false) {
    const unitPrice = parseUnitPrice(r.거래처);
    const weight = parseWeight(r.거래처);
    const dateRow = isSalesPage
        ? `<div class="mc-row"><span class="mc-label">단가</span>${formatUnitPrice(unitPrice)}</div>`
        : `<div class="mc-row"><span class="mc-label">예약일</span>${safeValue(r.홀딩일자)}</div>`;
    const weightRow = isSalesPage
        ? `<div class="mc-row"><span class="mc-label">중량</span>${formatWeight(weight)}</div>`
        : "";
    const totalRow = isSalesPage && unitPrice !== null && weight !== null
        ? `<div class="mc-row"><span class="mc-label">총금액</span>${formatUnitPrice(unitPrice * weight)}</div>`
        : "";
    const clientDisplay = isSalesPage ? clientPrefix(r.거래처) : safeValue(r.거래처);
    const completed = isSalesPage && r.status === "COMPLETED";
    const access = isSalesPage ? salesAccess(r) : { canEdit: true, canOthers: true };
    return `
        <div class="mobile-card reservation-card${completed ? " sales-completed-row" : ""}" data-reservation-id="${r.id}">
            <div class="mc-header">
                ${noteBtn(r, isSalesPage, access.canOthers)}
                ${isSalesPage && needsRegister(r) && access.canOthers ? `<label class="mc-register-label">${registerCheckboxHtml(r, access.canOthers)} 등록완료</label>` : ""}
                <span class="mc-name">${safeValue(r.상품명)}</span>
                ${whTag(r.창고)}
            </div>
            <div class="mc-tags">
                ${safeValue(r.브랜드) ? `<span class="s-tag">${safeValue(r.브랜드)}</span>` : ""}
                ${safeValue(r.등급)   ? `<span class="s-tag">${safeValue(r.등급)}</span>`   : ""}
                ${safeValue(r.ESTNO)  ? `<span class="s-tag">${safeValue(r.ESTNO)}</span>`  : ""}
            </div>
            <div class="mc-hero">
                <div class="mc-qty">${safeValue(r.수량) || 0}<span class="mc-qty-unit">박스</span></div>
            </div>
            <div class="mc-info">
                <div class="mc-row"><span class="mc-label">담당자</span>${safeValue(r.담당자) || "(미지정)"}</div>
                <div class="mc-row"><span class="mc-label">실재고</span>${safeValue(r.재고)}</div>
                <div class="mc-row"><span class="mc-label">가용재고</span>${availableCell(r.가용재고)}</div>
                ${dateRow}
                ${weightRow}
                ${totalRow}
                ${safeValue(r.출고일) ? `<div class="mc-row"><span class="mc-label">출고일</span>${safeValue(r.출고일)}</div>` : ""}
                ${clientDisplay ? `<div class="mc-row"><span class="mc-label">거래처</span>${clientDisplay}</div>` : ""}
                ${isSalesPage && safeValue(r.비고) ? `<div class="mc-row mc-full"><span class="mc-label">비고</span>${safeValue(r.비고)}</div>` : ""}
                ${safeValue(r.BL) ? `<div class="mc-row mc-full"><span class="mc-label">BL</span>${safeValue(r.BL)}</div>` : ""}
            </div>
            <div class="reservation-card-actions">
                ${completed || !access.canEdit ? "" : `<button class="edit-reservation-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}" data-release="${attrEscape(r.출고일)}" data-client="${attrEscape(r.거래처)}" data-remark="${attrEscape(r.비고)}" data-sales="${isSalesPage ? "1" : ""}">${isSalesPage ? "출고변경" : "예약변경"}</button>`}
                ${access.canOthers ? `<button class="use-reservation-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}" data-sales="${isSalesPage ? "1" : ""}" data-needs-register="${isSalesPage && needsRegisterBlock(r) ? "1" : ""}">${isSalesPage ? "출고완료" : "사용완료"}</button>` : ""}
                ${completed || !access.canOthers ? "" : `<button class="cancel-reservation-btn" data-id="${r.id}" data-sales="${isSalesPage ? "1" : ""}">${isSalesPage ? "출고취소" : "예약취소"}</button>`}
                ${isSalesPage || !access.canOthers ? "" : `<button class="register-outbound-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}">출고등록</button>`}
            </div>
        </div>
    `;
}

function reservationRowHtml(r, isSalesPage = false) {
    const unitPrice = parseUnitPrice(r.거래처);
    const weight = parseWeight(r.거래처);
    const dateCell = isSalesPage
        ? `<td>${formatUnitPrice(unitPrice)}</td>`
        : `<td>${safeValue(r.홀딩일자)}</td>`;
    const weightCell = isSalesPage ? `<td>${formatWeight(weight)}</td>` : "";
    const totalCell = isSalesPage
        ? `<td>${(unitPrice !== null && weight !== null) ? formatUnitPrice(unitPrice * weight) : ""}</td>`
        : "";
    const clientDisplay = isSalesPage ? clientPrefix(r.거래처) : safeValue(r.거래처);
    const completed = isSalesPage && r.status === "COMPLETED";
    const access = isSalesPage ? salesAccess(r) : { canEdit: true, canOthers: true };
    return `
        <tr data-reservation-id="${r.id}"${completed ? ' class="sales-completed-row"' : ""}>
            <td class="reservation-note-cell">${noteBtn(r, isSalesPage, access.canOthers)}</td>
            ${isSalesPage ? `<td class="${access.canEdit ? "sales-remark-cell" : ""}" data-id="${r.id}" data-remark="${attrEscape(r.비고)}" title="${access.canEdit ? "더블클릭해서 수정" : ""}">${safeValue(r.비고)}</td>` : ""}
            ${isSalesPage ? `<td class="reservation-register-cell">${registerCheckboxHtml(r, access.canOthers)}</td>` : ""}
            <td>${safeValue(r.담당자) || "(미지정)"}</td>
            <td>${safeValue(r.상품명)}</td>
            <td>${safeValue(r.브랜드)}</td>
            <td>${safeValue(r.등급)}</td>
            <td>${safeValue(r.ESTNO)}</td>
            <td>${safeValue(r.BL)}</td>
            <td>${whTag(r.창고)}</td>
            <td>${safeValue(r.수량)}</td>
            <td>${safeValue(r.재고)}</td>
            <td>${availableCell(r.가용재고)}</td>
            <td>${clientDisplay}</td>
            ${dateCell}
            ${weightCell}
            ${totalCell}
            <td>${safeValue(r.출고일)}</td>
            <td class="reservation-row-actions-cell">
                <div class="reservation-row-actions">
                    ${completed || !access.canEdit ? "" : `<button class="edit-reservation-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}" data-release="${attrEscape(r.출고일)}" data-client="${attrEscape(r.거래처)}" data-remark="${attrEscape(r.비고)}" data-sales="${isSalesPage ? "1" : ""}">${isSalesPage ? "출고변경" : "예약변경"}</button>`}
                    ${access.canOthers ? `<button class="use-reservation-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}" data-sales="${isSalesPage ? "1" : ""}" data-needs-register="${isSalesPage && needsRegisterBlock(r) ? "1" : ""}">${isSalesPage ? "출고완료" : "사용완료"}</button>` : ""}
                    ${completed || !access.canOthers ? "" : `<button class="cancel-reservation-btn" data-id="${r.id}" data-sales="${isSalesPage ? "1" : ""}">${isSalesPage ? "출고취소" : "예약취소"}</button>`}
                    ${isSalesPage || !access.canOthers ? "" : `<button class="register-outbound-btn" data-id="${r.id}" data-qty="${safeValue(r.수량) || 0}">출고등록</button>`}
                </div>
            </td>
        </tr>
    `;
}

// sales.html "추가" 버튼 — 팝업 대신 엑셀처럼 표 맨 위에 입력행을 띄운다(2026-08-14).
// 열 순서는 reservationsHead(true)와 동일해야 함: 비고,등록완료,담당자,상품명,브랜드,
// 등급,ESTNO,BL,창고,수량,실재고,가용재고,거래처,단가,중량,총금액,출고일,액션(18칸,
// 2026-08-19 비고를 "!" 옆으로 이동). 실재고/가용재고/총금액은 아직 어떤 재고인지
// 확정 전이라 입력칸 없이 빈칸으로 두고, 등록완료도 신규 입력행 단계에선 아직
// 창고가 정해지지 않아 빈칸.
export function outboundInsertRowHtml() {
    return `
        <tr class="outbound-insert-row">
            <td></td>
            <td><input type="text" class="ob-in-remark cell-input" placeholder="비고"></td>
            <td></td>
            <td>${employeeSelect("ob-in-manager")}</td>
            <td><input type="text" class="ob-in-name cell-input" placeholder="상품명"></td>
            <td><input type="text" class="ob-in-brand cell-input" placeholder="브랜드"></td>
            <td><input type="text" class="ob-in-grade cell-input" placeholder="등급"></td>
            <td><input type="text" class="ob-in-estno cell-input" placeholder="ESTNO"></td>
            <td><input type="text" class="ob-in-bl cell-input" placeholder="BL"></td>
            <td><input type="text" class="ob-in-wh cell-input" placeholder="창고"></td>
            <td><input type="number" class="ob-in-qty cell-input" min="1" value="1"></td>
            <td></td>
            <td></td>
            <td><input type="text" class="ob-in-client cell-input" placeholder="거래처명"></td>
            <td><input type="number" class="ob-in-price cell-input" min="0" placeholder="단가"></td>
            <td><input type="number" step="0.01" min="0" class="ob-in-weight cell-input" placeholder="중량"></td>
            <td></td>
            <td><input type="date" class="ob-in-date cell-input" title="비우면 오늘"></td>
            <td class="reservation-row-actions-cell">
                <div class="reservation-row-actions">
                    <button class="save-outbound-insert-btn">저장</button>
                    <button class="cancel-outbound-insert-btn">취소</button>
                </div>
            </td>
        </tr>
    `;
}

// 열 너비는 실제 값 길이 기준(2026-08-14) — BL이 13~20자로 가장 길고, 등급/수량/
// 실재고/가용재고는 짧은 숫자·코드라 좁게 잡음. 공통 열(담당자~거래처)은 두 모드에서
// 폭이 동일하고, 마지막 구간(단가/총금액/예약일/출고일/액션)만 열 개수에 맞춰
// 100%를 재분배한다. table-layout은 auto로 둬서(강제 fixed 아님) 값이 넘치면
// 브라우저가 알아서 더 넓혀줌 — 그래도 넘치면 .reservations-container의 가로
// 스크롤로 커버. 액션 칸은 버튼 3개(예약변경/사용완료/홀딩취소)가 안 잘리게
// 넉넉히 잡음.
// isSalesPage: sales.html에서는 "예약일" 대신 "단가"+"중량"+"총금액"(단가×중량,
// 자동계산) 세 칸을 보여준다(단가/중량은 예약 데이터에 아직 없는 값이라 빈칸일
// 수 있고 그러면 총금액도 빈칸).
function reservationsHead(isSalesPage = false) {
    // 타창고매출현황(2026-08-19) — 비고를 "!" 바로 옆으로 옮기고, 상품명/BL은
    // 줄어든 만큼(안 잘리는 선에서 최소한만) 재고 관련 열(수량/실재고/가용재고)과
    // 출고일/액션에 더 배분. table-layout이 auto라 % 미만이어도 내용이 넘치면
    // 브라우저가 알아서 넓혀서 실제로 잘리진 않는다(가로 스크롤로 커버).
    if (isSalesPage) {
        return `
    <colgroup>
        <col style="width:4%">  <!--전달사항-->
        <col style="width:3%">  <!--비고-->
        <col style="width:4%">  <!--등록완료-->
        <col style="width:5%">  <!--담당자-->
        <col style="width:8%">  <!--상품명-->
        <col style="width:5%">  <!--브랜드-->
        <col style="width:3%">  <!--등급-->
        <col style="width:4%">  <!--ESTNO-->
        <col style="width:11%"> <!--BL-->
        <col style="width:5%">  <!--창고-->
        <col style="width:4%">  <!--수량-->
        <col style="width:4%">  <!--실재고-->
        <col style="width:5%">  <!--가용재고-->
        <col style="width:6%">  <!--거래처-->
        <col style="width:4%">  <!--단가-->
        <col style="width:4%">  <!--중량-->
        <col style="width:5%">  <!--총금액-->
        <col style="width:7%">  <!--출고일-->
        <col style="width:9%">  <!--액션-->
    </colgroup>
    <thead>
        <tr>
            <th></th><th>비고</th><th>등록완료</th>
            <th>담당자</th><th>상품명</th><th>브랜드</th><th>등급</th><th>ESTNO</th>
            <th>BL</th><th>창고</th><th>수량</th><th>실재고</th><th>가용재고</th>
            <th>거래처</th><th>단가</th><th>중량</th><th>총금액</th><th>출고일</th><th>액션</th>
        </tr>
    </thead>
`;
    }
    return `
    <colgroup>
        <col style="width:4%">  <!--전달사항-->
        <col style="width:7%">  <!--담당자-->
        <col style="width:9%">  <!--상품명-->
        <col style="width:6%">  <!--브랜드-->
        <col style="width:3%">  <!--등급-->
        <col style="width:4%">  <!--ESTNO-->
        <col style="width:12%"> <!--BL-->
        <col style="width:6%">  <!--창고-->
        <col style="width:4%">  <!--수량-->
        <col style="width:4%">  <!--실재고-->
        <col style="width:5%">  <!--가용재고-->
        <col style="width:10%"> <!--거래처-->
        <col style="width:7%">  <!--예약일-->
        <col style="width:6%">  <!--출고일-->
        <col style="width:13%"> <!--액션-->
    </colgroup>
    <thead>
        <tr>
            <th></th>
            <th>담당자</th><th>상품명</th><th>브랜드</th><th>등급</th><th>ESTNO</th>
            <th>BL</th><th>창고</th><th>수량</th><th>실재고</th><th>가용재고</th>
            <th>거래처</th><th>예약일</th><th>출고일</th><th>액션</th>
        </tr>
    </thead>
`;
}

// 타창고매출현황 탭(2026-08-18, sales.html에서 warehouse_main.html 안 탭으로 이관)은
// 예약현황 탭 컴포넌트를 재사용하되 담당자 제한 없이 전체 + 출고일이 오늘인 것만
// 고정으로 보여준다 — 사용자가 조정할 필터가 아니라 이 탭의 고정 조건이라 담당자
// 드롭다운/출고일 선택기 UI 자체를 안 띄운다. 출고일은 <input type="date"> 값과
// 같은 "YYYY-MM-DD" 형식으로 저장되므로 그 형식으로 오늘 날짜를 만든다.
function todayISOStr() {
    const d = new Date();
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 예약/출고 현황 탭 — 재고장 표와 같은 툴바(검색1·검색2 + 상품명/브랜드/창고
// 드롭다운)를 그대로 재사용해서 필터링한다(2026-08-18). "상태" 드롭다운(예약/
// 동결/이고 등)은 재고장 행의 상태값이지 예약/출고 행에는 없는 값이라 여기선
// 적용하지 않는다 — 적용하면 뭘 골라도 결과가 항상 0건이 되는 함정이라 뺌.
const RESERVATION_SEARCHABLE_KEYS = ["담당자", "상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "거래처", "비고", "홀딩일자", "출고일"];

function matchesReservationKeyword(r, kw) {
    return RESERVATION_SEARCHABLE_KEYS.some(key => {
        const value = r[key];
        if (value == null) return false;
        const text = cleanText(value).toLowerCase();
        if (text.includes(kw)) return true;
        return Object.entries(BRAND_ALIASES).some(([ko, en]) =>
            ko.includes(kw) && text === en.toLowerCase()
        );
    });
}

function filterReservationRows(rows) {
    const keyword = cleanText(dom.searchInput?.value || "").toLowerCase();
    const keyword2 = cleanText(dom.searchInput2?.value || "").toLowerCase();
    const warehouse = document.querySelector(".show-warehouse")?.value || "";
    const productName = document.querySelector(".show-product-name")?.value || "";
    const brand = document.querySelector(".show-brand")?.value || "";

    let data = rows;
    if (keyword) data = data.filter(r => matchesReservationKeyword(r, keyword));
    if (keyword2) data = data.filter(r => matchesReservationKeyword(r, keyword2));
    if (warehouse && warehouse !== "non") data = data.filter(r => r.창고 === warehouse);
    if (productName && productName !== "non") data = data.filter(r => r.상품명 === productName);
    if (brand && brand !== "non") data = data.filter(r => r.브랜드 === brand);
    return data;
}

export async function renderReservationsTab() {
    const container = document.querySelector(".reservations-container");
    const listEl = document.getElementById("reservations-list");
    if (!container || !listEl || container.style.display === "none") return;

    const user = getStoredUser();
    const isEditor = hasEditorAccess(user?.권한);

    let rows = [];
    try {
        rows = await getAllReservations();
    } catch (e) {
        listEl.innerHTML = `<p class="reservations-empty">예약 현황을 불러오지 못했습니다.</p>`;
        return;
    }

    if (!isEditor) {
        rows = rows.filter(r => r.담당자 === user?.이름);
    }

    // 출고일 필터 — 편집자/사원 공통(2026-08-13).
    // rows 자체를 걸러서 아래 담당자 그룹핑/건수 표시에도 필터 결과가 그대로 반영되게 한다.
    if (state.reservationsDateFilter) {
        rows = rows.filter(r => safeValue(r.출고일) === state.reservationsDateFilter);
    }
    const dateFilterHtml = `
        <label for="reservations-date-filter">출고일</label>
        <input type="date" id="reservations-date-filter" class="reservations-filter-select" value="${state.reservationsDateFilter}">
        ${state.reservationsDateFilter ? `<button type="button" class="reservations-date-filter-clear" title="출고일 필터 해제">✕</button>` : ""}
    `;

    // 툴바 검색1·검색2 + 상품명/브랜드/창고 드롭다운 적용(2026-08-18) — 재고장
    // 표에서 쓰던 그 툴바를 예약 현황 탭에서도 그대로 재사용.
    rows = filterReservationRows(rows);

    if (isEditor) {
        const groups = {};
        rows.forEach(r => {
            const key = r.담당자 || "(미지정)";
            (groups[key] = groups[key] || []).push(r);
        });
        const allNames = Object.keys(groups).sort((a, b) => a.localeCompare(b, "ko"));

        // 이전에 골랐던 담당자가 이번엔 예약이 하나도 없으면(전부 취소 등) 필터 초기화
        if (state.reservationsFilter && !allNames.includes(state.reservationsFilter)) {
            state.reservationsFilter = "";
        }
        const filterHtml = `
            <div class="reservations-filter-bar">
                <label for="reservations-filter">담당자</label>
                <select id="reservations-filter" class="reservations-filter-select">
                    <option value="">전체 (${rows.length}건)</option>
                    ${allNames.map(name => `<option value="${name}" ${name === state.reservationsFilter ? "selected" : ""}>${name} (${groups[name].length}건)</option>`).join("")}
                </select>
                ${dateFilterHtml}
            </div>
        `;

        const names = state.reservationsFilter ? [state.reservationsFilter] : allNames;
        state.filteredReservations = names.flatMap(name => groups[name] || []);
        const body = names.length ? names.map(name => `
            <div class="reservations-group">
                <h3>${name} <span class="reservations-group-count">${groups[name].length}건</span></h3>
                <table class="reservations-table">
                    ${reservationsHead()}
                    <tbody>${groups[name].map(r => reservationRowHtml(r)).join("")}</tbody>
                </table>
                <div class="reservations-mobile-list">${groups[name].map(r => reservationCardHtml(r)).join("")}</div>
            </div>
        `).join("") : `<p class="reservations-empty">조건에 맞는 예약이 없습니다.</p>`;

        listEl.innerHTML = filterHtml + body;
    } else {
        state.filteredReservations = rows;
        const filterHtml = `<div class="reservations-filter-bar">${dateFilterHtml}</div>`;
        const empty = `<p class="reservations-empty">조건에 맞는 예약이 없습니다.</p>`;
        listEl.innerHTML = filterHtml + (rows.length ? `
            <table class="reservations-table">
                ${reservationsHead()}
                <tbody>${rows.map(r => reservationRowHtml(r)).join("")}</tbody>
            </table>
            <div class="reservations-mobile-list">${rows.map(r => reservationCardHtml(r)).join("")}</div>
        ` : empty);
    }
}

// 타창고매출현황 탭(2026-08-18, sales.html에서 이관) — 담당자 제한 없이 전체 +
// 출고일이 오늘인 outbound만 고정으로 보여준다. renderReservationsTab()과 컴포넌트를
// 공유하지만 데이터 소스(outbound API)와 레이아웃(그룹핑 없는 플랫 표 + "추가"
// 입력행)이 달라서 별도 함수로 둔다.
export async function renderSalesTab() {
    const container = document.querySelector(".sales-container");
    const listEl = document.getElementById("sales-list");
    if (!container || !listEl || container.style.display === "none") return;

    let rows = [];
    try {
        // outbound(타창고매출현황)는 예약과 완전히 분리된 별도 저장소(2026-08-14) —
        // 이 탭은 예약 API가 아니라 outbound API만 쓴다. 서버가 조회 시점에
        // 출고일=오늘인 예약을 outbound로 옮긴 뒤 내려주므로, 서버가 이미 오늘
        // 것만 담고 있어 별도 날짜 필터가 원래는 필요 없지만, 하루가 지나도록
        // 수정 안 된 outbound 잔여물이 계속 보이는 걸 막기 위해 클라이언트에서도
        // 한 번 더 오늘 날짜로 걸러준다.
        rows = await getAllOutbound();
    } catch (e) {
        listEl.innerHTML = `<p class="reservations-empty">출고 현황을 불러오지 못했습니다.</p>`;
        return;
    }

    // 출고일 필터(2026-08-19) — 안 고르면 오늘(기존 고정 동작 그대로), 고르면 그 날짜.
    // outbound 잔여물(하루 지나도록 완료/취소 안 된 것)도 이걸로 확인 가능해짐.
    const salesDate = state.salesDateFilter || todayISOStr();
    rows = rows.filter(r => safeValue(r.출고일) === salesDate);
    rows = filterReservationRows(rows);

    // 출고완료(status=COMPLETED) 행은 맨 뒤로 보내고 회색 배경 — 그 안에서는
    // 원래 순서 그대로 유지(2026-08-14, DB status 토글로 새로고침해도 유지됨).
    rows = [...rows].sort((a, b) =>
        Number(a.status === "COMPLETED") - Number(b.status === "COMPLETED")
    );
    state.filteredReservations = rows;
    const dateFilterHtml = `
        <div class="reservations-filter-bar">
            <label for="sales-date-filter">출고일</label>
            <input type="date" id="sales-date-filter" class="reservations-filter-select" value="${salesDate}">
            ${state.salesDateFilter ? `<button type="button" class="sales-date-filter-clear" title="오늘로 초기화">✕</button>` : ""}
        </div>
    `;
    // "추가" 버튼으로 표 맨 위에 입력행을 띄우므로(2026-08-14), 데이터가 0건이어도
    // 표 자체(헤더 + 빈 입력행 tbody)는 항상 그려둔다.
    const emptyMsg = rows.length ? "" : `<p class="reservations-empty">${salesDate} 출고 항목이 없습니다.</p>`;
    listEl.innerHTML = `
        ${dateFilterHtml}
        <table class="reservations-table">
            ${reservationsHead(true)}
            <tbody id="outbound-insert-rows"></tbody>
            <tbody>${rows.map(r => reservationRowHtml(r, true)).join("")}</tbody>
        </table>
        ${emptyMsg}
        <div class="reservations-mobile-list">${rows.map(r => reservationCardHtml(r, true)).join("")}</div>
    `;
}


