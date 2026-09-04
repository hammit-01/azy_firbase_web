import { PRICE_FIELDS, reservationListItemsHtml } from "./table.js";
import { dispatcherSelect, moveWarehouseSelect, employeeSelect, stateSelect } from "./panel.js";

// BL이 영문+숫자 조합이면(실제 크롤링 BL 형식) 재고 매칭 없이 바로 추가하는
// "추가" 팝업 대상이 아니다(2026-09-04 사용자 지정: 매칭 없이 그냥 추가하는
// 대신, 진짜 재고 BL처럼 보이면 막는다) — 타창고매출현황/창고이동 공용.
export function looksLikeRealBl(bl) {
    return /[A-Za-z]/.test(bl) && /[0-9]/.test(bl);
}

export function showToast(msg, type = "success") {
    let t = document.getElementById("toast-msg");
    if (!t) {
        t = document.createElement("div");
        t.id = "toast-msg";
        document.body.appendChild(t);
    }
    t.className = "toast toast-" + type;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), type === "error" ? 3500 : 2200);
}

export function showError(msg) {
    showToast(msg, "error");
}

// 모든 팝업 공용 배경 클릭/Esc/Enter 처리(2026-09-04 사용자 요청).
// - 바깥클릭 닫기: mousedown이 오버레이 자체에서 시작했을 때만 닫는다 — 입력칸
//   안에서 텍스트를 드래그 선택하다 마우스가 팝업 밖으로 나가서 놓이면(mouseup이
//   오버레이에서 발생) click의 target도 오버레이가 돼버려 그냥 닫히던 버그 수정.
// - Esc: onCancel(보통 close(null)/close())을 그대로 부른다.
// - Enter: onSubmit이 있으면 그 버튼을 눌러 각 모달의 기존 검증 로직을 그대로
//   태운다 — textarea(줄바꿈 용도)와 select(방향키로 옵션 고르는 중 오작동 방지)
//   안에서는 무시.
function wireModalOverlay(overlay, { onCancel, onSubmit } = {}) {
    let mouseDownOnOverlay = false;
    overlay.addEventListener("mousedown", (e) => { mouseDownOnOverlay = e.target === overlay; });
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay && mouseDownOnOverlay) onCancel?.();
        mouseDownOnOverlay = false;
    });
    overlay.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { e.preventDefault(); onCancel?.(); return; }
        if (e.key === "Enter" && onSubmit && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "SELECT") {
            e.preventDefault();
            onSubmit();
        }
    });
    autoFocusFirstField(overlay);
}

// 팝업 뜨자마자 바로 입력할 수 있게 첫 입력칸에 포커스(2026-09-04 사용자 요청) —
// 입력칸이 없는(조회 전용) 팝업은 대신 첫 버튼에 포커스해서 Enter/Space로 바로
// 확인 가능하게. 텍스트 입력칸이면 기존 값을 전체 선택해서 바로 덮어쓸 수 있게.
function autoFocusFirstField(overlay) {
    const field = overlay.querySelector("input, select, textarea");
    if (field) {
        field.focus();
        if (typeof field.select === "function") field.select();
    } else {
        overlay.querySelector("button")?.focus();
    }
}

// 여러 행을 한 번에 입력하는 팝업 공용 골격(2026-09-04, 사용자 요청 — 표 안에서
// 바로 입력하던 방식 대신 팝업 + "+ 행 추가" 버튼으로 바꿈). rowFieldsHtml()이
// 빈 행 하나의 입력칸 HTML을 돌려주면, 여기서 행 추가/삭제를 붙인다.
// "+"/"✕" 버튼에 포커스된 채 Enter를 누르면 원래 그 버튼을 누른 것처럼 동작해야
// 하는데, wireModalOverlay의 전역 Enter 핸들러가 먼저 가로채 전체 폼을 저장해
// 버리는 문제가 있어(2026-09-04 실측) 버튼 자신의 keydown에서 stopPropagation
// 으로 막아준다.
function _wireMultiRowInsert(overlay, rowFieldsHtml) {
    const rowsBody = overlay.querySelector(".multi-insert-rows");
    const updateRemoveButtons = () => {
        const rows = rowsBody.querySelectorAll(".multi-insert-row");
        rows.forEach(r => {
            const btn = r.querySelector(".multi-insert-remove-row");
            if (btn) btn.style.display = rows.length > 1 ? "" : "none";
        });
    };
    const addRow = () => {
        const div = document.createElement("div");
        div.className = "multi-insert-row";
        div.innerHTML = rowFieldsHtml() + `<button type="button" class="multi-insert-remove-row" title="이 행 삭제">✕</button>`;
        rowsBody.appendChild(div);
        updateRemoveButtons();
        div.querySelector("input, select")?.focus();
    };
    rowsBody.addEventListener("click", (e) => {
        if (e.target.classList.contains("multi-insert-remove-row")) {
            e.target.closest(".multi-insert-row")?.remove();
            updateRemoveButtons();
        }
    });
    rowsBody.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.classList.contains("multi-insert-remove-row")) e.stopPropagation();
    });
    const addBtn = overlay.querySelector(".multi-insert-add-row");
    addBtn?.addEventListener("click", addRow);
    addBtn?.addEventListener("keydown", (e) => { if (e.key === "Enter") e.stopPropagation(); });
    updateRemoveButtons();
}

// 예약변경 모달 — 수량/출고일/거래처를 한 번에 수정(2026-08-14, "수량변경"에서 확장).
// current: {수량, 출고일, 거래처}. showPrice=true(sales.html)면 거래처 대신
// 거래처명(prefix)+단가+중량 입력칸 세 개로 나눠서 받는다 — 단가/중량은 자체
// 컬럼이 없어서 거래처 문자열에 "이름 숫자원 숫자kg"로 합쳐 저장하기 때문
// (table.js의 buildClientWithDetails와 짝). showPrice면 비고(outbound 전용 컬럼)도
// 같이 받는다(2026-08-19). canRemark=false면 비고는 사원이 본인 담당 건이어도
// 못 고치게 입력칸 자체를 안 보여준다(2026-08-20) — 편집자/관리자만 true.
// 저장 누르면 {수량, 출고일, 거래처}(showPrice면 {수량, 출고일, 거래처명, 단가,
// 중량, [canRemark면 비고]}) 객체로 resolve, 취소/바깥클릭이면 null.
export function showEditReservationModal(current, { showPrice = false, canRemark = false } = {}) {
    return new Promise(resolve => {
        const clientFieldHtml = showPrice
            ? `<label>거래처명<input type="text" class="edit-res-client" value="${(current.거래처명 ?? "").replace(/"/g, "&quot;")}"></label>` +
              `<label>단가<input type="number" class="edit-res-price" min="0" value="${current.단가 ?? ""}"></label>` +
              `<label>중량(kg)<input type="number" step="0.01" min="0" class="edit-res-weight" value="${current.중량 ?? ""}"></label>` +
              (canRemark ? `<label>비고<input type="text" class="edit-res-remark" value="${(current.비고 ?? "").replace(/"/g, "&quot;")}"></label>` : "")
            : `<label>거래처<input type="text" class="edit-res-client" value="${(current.거래처 ?? "").replace(/"/g, "&quot;")}"></label>`;

        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal">` +
            `<p class="confirm-msg">예약 변경</p>` +
            `<div class="edit-reservation-form">` +
            `<label>수량<input type="number" class="edit-res-qty" min="1" value="${current.수량 ?? ""}"></label>` +
            `<label>출고일<input type="date" class="edit-res-date" value="${current.출고일 ?? ""}"></label>` +
            clientFieldHtml +
            `</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">저장</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const qty = Number(overlay.querySelector(".edit-res-qty").value);
            const result = {
                수량: qty,
                출고일: overlay.querySelector(".edit-res-date").value,
            };
            if (showPrice) {
                result.거래처명 = overlay.querySelector(".edit-res-client").value.trim();
                result.단가 = overlay.querySelector(".edit-res-price").value;
                result.중량 = overlay.querySelector(".edit-res-weight").value;
                if (canRemark) result.비고 = overlay.querySelector(".edit-res-remark").value.trim();
            } else {
                result.거래처 = overlay.querySelector(".edit-res-client").value.trim();
            }
            close(result);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 출고등록 모달 — 예약 행에서 일부/전체 수량을 outbound로 옮길 때 사용재고(수량)/
// 출고일자/거래처를 입력받는다(2026-08-14). current: {수량}(예약의 현재 수량 =
// 입력 max/기본값). 저장 누르면 {수량, 출고일, 거래처} 객체로 resolve, 취소/
// 바깥클릭이면 null. 기존 edit-reservation-modal 스타일 재사용.
export function showRegisterOutboundModal(current) {
    return new Promise(resolve => {
        const maxQty = Number(current.수량) || 0;
        // new Date().toISOString()은 UTC 기준이라 자정~오전 9시(KST) 사이엔 하루 전
        // 날짜가 나옴(2026-08-19 수정) — 로컬 날짜로 직접 계산.
        const now = new Date();
        const pad = n => String(n).padStart(2, "0");
        const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal">` +
            `<p class="confirm-msg">출고등록</p>` +
            `<div class="edit-reservation-form">` +
            `<label>사용재고<input type="number" class="reg-ob-qty" min="1" max="${maxQty}" value="${maxQty}"></label>` +
            `<label>출고일<input type="date" class="reg-ob-date" value="${today}" min="${today}"></label>` +
            `<label>거래처<input type="text" class="reg-ob-client" value=""></label>` +
            `</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">등록</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const qty = Number(overlay.querySelector(".reg-ob-qty").value);
            if (!qty || qty < 1 || qty > maxQty) {
                showError(`사용재고는 1~${maxQty} 사이여야 합니다`);
                return;
            }
            const releaseDate = overlay.querySelector(".reg-ob-date").value;
            if (releaseDate && releaseDate < today) {
                showError("출고일은 오늘 이전으로 선택할 수 없습니다");
                return;
            }
            close({
                수량: qty,
                출고일: releaseDate,
                거래처: overlay.querySelector(".reg-ob-client").value.trim(),
            });
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 창고이동 모달 — 예약현황 행의 "이동" 버튼(2026-09-04, 관리자+8001 테스트 기능).
// showRegisterOutboundModal과 동일한 골격 — 예약 수량 중 일부/전체(current.수량이
// 입력 max/기본값)를 창고이동으로 등록한다. 담당자/거래처는 예약에 이미 있어서
// 여기서 따로 안 받는다(백엔드가 예약에서 그대로 가져다 씀). 배차자="새벽"이면
// 창고이동 등록 팝업과 동일하게 이동일자 선택란을 숨기고 다음날로 자동 처리—
// 실제 값 계산은 저장 시 호출부(events.js)가 한다. 저장 누르면
// {수량, 배차자, 이동일자, 이동창고} 객체로 resolve, 취소/바깥클릭이면 null.
export function showMoveToWarehouseModal(current) {
    return new Promise(resolve => {
        const maxQty = Number(current.수량) || 0;
        const tomorrow = new Date(Date.now() + 86400000);
        const pad = n => String(n).padStart(2, "0");
        const tomorrowStr = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`;
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal">` +
            `<p class="confirm-msg">창고이동 등록</p>` +
            `<div class="edit-reservation-form">` +
            `<label>수량<input type="number" class="move-res-qty" min="1" max="${maxQty}" value="${maxQty}"></label>` +
            `<label>배차자${dispatcherSelect("move-res-dispatcher")}</label>` +
            `<label class="move-res-date-field">이동일자<input type="date" class="move-res-date" value="${tomorrowStr}"></label>` +
            `<label>이동창고${moveWarehouseSelect("move-res-warehouse")}</label>` +
            `</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">등록</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        overlay.querySelector(".move-res-dispatcher").addEventListener("change", (e) => {
            overlay.querySelector(".move-res-date-field").style.display = e.target.value === "새벽" ? "none" : "";
        });

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const qty = Number(overlay.querySelector(".move-res-qty").value);
            if (!qty || qty < 1 || qty > maxQty) {
                showError(`수량은 1~${maxQty} 사이여야 합니다`);
                return;
            }
            const dispatcher = overlay.querySelector(".move-res-dispatcher").value;
            const warehouse = overlay.querySelector(".move-res-warehouse").value;
            if (!dispatcher || !warehouse) {
                showError("배차자와 이동창고를 선택하세요");
                return;
            }
            close({
                수량: qty,
                배차자: dispatcher,
                이동일자: dispatcher === "새벽" ? "" : overlay.querySelector(".move-res-date").value,
                이동창고: warehouse,
            });
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 재고장 메인 "추가" 팝업(2026-09-04 재설계 — 표 맨 위 인라인 입력행 대신
// 다른 "추가" 기능들과 같은 팝업 + "+ 행 추가" 방식으로 통일). 저장 누르면
// [{name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight, dataState,
// memo}, ...] 배열로 resolve(빈 행은 자동 제외, insertData의 파라미터 이름
// 그대로 맞춤), 취소/바깥클릭이면 null.
export function showInventoryInsertModal() {
    return new Promise(resolve => {
        const rowFieldsHtml = () => `
            <div class="edit-reservation-form">
                <label class="mi-field-lg">상품명<input type="text" class="mi-name" placeholder="상품명"></label>
                <label class="mi-field-md">브랜드<input type="text" class="mi-brand"></label>
                <label class="mi-field-xs">등급<input type="text" class="mi-grade"></label>
                <label class="mi-field-sm">ESTNO<input type="text" class="mi-estno"></label>
                <label class="mi-field-xs">재고<input type="number" min="1" class="mi-qty"></label>
                <label class="mi-field-lg">BL<input type="text" class="mi-bl" placeholder="BL"></label>
                <label class="mi-field-sm">창고<input type="text" class="mi-wh" placeholder="창고"></label>
                <label class="mi-field-md">유통기한<input type="date" class="mi-duedate"></label>
                <label class="mi-field-xs">평중<input type="number" step="0.01" class="mi-weight"></label>
                <label class="mi-field-md">상태${stateSelect("mi-state")}</label>
                <label class="mi-field-lg">비고<input type="text" class="mi-memo" placeholder="비고"></label>
            </div>
        `;
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal multi-insert-modal">` +
            `<p class="confirm-msg">재고 추가</p>` +
            `<div class="multi-insert-rows"><div class="multi-insert-row">${rowFieldsHtml()}<button type="button" class="multi-insert-remove-row" title="이 행 삭제" style="display:none">✕</button></div></div>` +
            `<button type="button" class="multi-insert-add-row">+ 행 추가</button>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">저장</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);
        _wireMultiRowInsert(overlay, rowFieldsHtml);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const results = [];
            for (const row of overlay.querySelectorAll(".multi-insert-row")) {
                const val = sel => row.querySelector(sel)?.value.trim() ?? "";
                const name = val(".mi-name"), qty = val(".mi-qty"), bl = val(".mi-bl"), warehouse = val(".mi-wh");
                if (!name && !qty && !bl && !warehouse) continue; // 빈 채로 남은 여분 행은 건너뜀
                results.push({
                    name, brand: val(".mi-brand"), grade: val(".mi-grade"), estNo: val(".mi-estno"),
                    qty, bl, warehouse, dueDate: val(".mi-duedate"), weight: val(".mi-weight"),
                    dataState: row.querySelector(".mi-state")?.value || "",
                    memo: val(".mi-memo"),
                });
            }
            if (results.length === 0) { showError("최소 1건은 입력하세요."); return; }
            close(results);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 타창고매출현황 "추가" 팝업(2026-09-04 재설계 — 표 안에 입력행을 띄우던 방식
// 대신 팝업 + "+ 행 추가" 버튼으로 여러 건을 한 번에 입력). 재고 매칭 없이
// create_outbound_manual로 바로 들어가므로 유통기한/상태는 안 받는다. 저장
// 누르면 [{상품명, BL, 창고, 수량, 브랜드, 등급, ESTNO, 담당자, 거래처, 비고,
// 출고일}, ...] 배열로 resolve(빈 행은 자동 제외), 취소/바깥클릭이면 null.
export function showOutboundManualInsertModal() {
    return new Promise(resolve => {
        const rowFieldsHtml = () => `
            <div class="edit-reservation-form">
                <label class="mi-field-lg">품목<input type="text" class="mi-name" placeholder="상품명"></label>
                <label class="mi-field-md">브랜드<input type="text" class="mi-brand"></label>
                <label class="mi-field-xs">등급<input type="text" class="mi-grade"></label>
                <label class="mi-field-sm">EST<input type="text" class="mi-estno"></label>
                <label class="mi-field-xs">수량<input type="number" class="mi-qty" min="1" value="1"></label>
                <label class="mi-field-lg">BL<input type="text" class="mi-bl" placeholder="BL"></label>
                <label class="mi-field-sm">창고<input type="text" class="mi-wh" placeholder="창고"></label>
                <label class="mi-field-md">담당자${employeeSelect("mi-manager")}</label>
                <label class="mi-field-md">거래처<input type="text" class="mi-client"></label>
                <label class="mi-field-lg">비고<input type="text" class="mi-remark"></label>
                <label class="mi-field-md">출고일<input type="date" class="mi-date" title="비우면 오늘"></label>
            </div>
        `;
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal multi-insert-modal">` +
            `<p class="confirm-msg">타창고매출현황 추가 — 타사 이체/출고분만 (재고 매칭 없이 바로 등록)</p>` +
            `<div class="multi-insert-rows"><div class="multi-insert-row">${rowFieldsHtml()}<button type="button" class="multi-insert-remove-row" title="이 행 삭제" style="display:none">✕</button></div></div>` +
            `<button type="button" class="multi-insert-add-row">+ 행 추가</button>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">저장</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);
        _wireMultiRowInsert(overlay, rowFieldsHtml);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const results = [];
            for (const row of overlay.querySelectorAll(".multi-insert-row")) {
                const val = sel => row.querySelector(sel)?.value.trim() ?? "";
                const 상품명 = val(".mi-name"), BL = val(".mi-bl"), 창고 = val(".mi-wh");
                const 수량 = Number(val(".mi-qty"));
                if (!상품명 && !BL && !창고) continue;
                if (!상품명 || !BL || !창고) { showError("품목/BL/창고는 필수입니다."); return; }
                if (!Number.isInteger(수량) || 수량 <= 0) { showError("올바른 수량을 입력하세요."); return; }
                if (looksLikeRealBl(BL)) { showError("타사 이체/출고분만 추가 가능합니다."); return; }
                results.push({
                    상품명, BL, 창고, 수량,
                    브랜드: val(".mi-brand"), 등급: val(".mi-grade"), ESTNO: val(".mi-estno"),
                    담당자: val(".mi-manager"), 거래처: val(".mi-client"),
                    비고: val(".mi-remark"), 출고일: val(".mi-date"),
                });
            }
            if (results.length === 0) { showError("최소 1건은 입력하세요."); return; }
            close(results);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 창고이동 "추가" 팝업(2026-09-04, 관리자+8001 테스트 기능) — showOutboundManual
// InsertModal과 동일한 골격이되 필드가 다르다(배차자/이동창고/실중량/매출처/
// 수정사항/평중 추가, 상태/유통기한/출고일 없음 — 재고 매칭·예약 생성 없이
// create_warehouse_move_manual로 바로 들어감). 이동일자는 입력칸 없이 호출부가
// 현재 보고 있는 날짜 필터(없으면 오늘)로 채운다. 저장 누르면 행 배열로
// resolve(빈 행은 자동 제외), 취소/바깥클릭이면 null.
export function showMoveManualInsertModal() {
    return new Promise(resolve => {
        const rowFieldsHtml = () => `
            <div class="edit-reservation-form">
                <label class="mi-field-lg">품목<input type="text" class="mi-name" placeholder="상품명"></label>
                <label class="mi-field-md">브랜드<input type="text" class="mi-brand"></label>
                <label class="mi-field-xs">등급<input type="text" class="mi-grade"></label>
                <label class="mi-field-sm">EST<input type="text" class="mi-estno"></label>
                <label class="mi-field-xs">수량<input type="number" class="mi-qty" min="1" value="1"></label>
                <label class="mi-field-lg">BL<input type="text" class="mi-bl" placeholder="BL"></label>
                <label class="mi-field-sm">출고창고<input type="text" class="mi-wh" placeholder="창고"></label>
                <label class="mi-field-md">배차자${dispatcherSelect("mi-dispatcher")}</label>
                <label class="mi-field-md">이동창고${moveWarehouseSelect("mi-move-wh")}</label>
                <label class="mi-field-xs">실중량<input type="number" step="0.01" min="0" class="mi-weight"></label>
                <label class="mi-field-md">담당자${employeeSelect("mi-manager")}</label>
                <label class="mi-field-md">매출처<input type="text" class="mi-client"></label>
                <label class="mi-field-lg">수정사항<input type="text" class="mi-note"></label>
                <label class="mi-field-xs">평중<input type="number" step="0.01" min="0" class="mi-avgweight"></label>
                <label class="mi-field-lg">비고<input type="text" class="mi-remark"></label>
            </div>
        `;
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal multi-insert-modal">` +
            `<p class="confirm-msg">창고이동 추가 — 타사 출고/기타 특이품분만 (재고 매칭 없이 바로 등록)</p>` +
            `<div class="multi-insert-rows"><div class="multi-insert-row">${rowFieldsHtml()}<button type="button" class="multi-insert-remove-row" title="이 행 삭제" style="display:none">✕</button></div></div>` +
            `<button type="button" class="multi-insert-add-row">+ 행 추가</button>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">저장</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);
        _wireMultiRowInsert(overlay, rowFieldsHtml);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const results = [];
            for (const row of overlay.querySelectorAll(".multi-insert-row")) {
                const val = sel => row.querySelector(sel)?.value.trim() ?? "";
                const 상품명 = val(".mi-name"), BL = val(".mi-bl"), 창고 = val(".mi-wh");
                const 수량 = Number(val(".mi-qty"));
                if (!상품명 && !BL && !창고) continue;
                if (!상품명 || !BL || !창고) { showError("품목/BL/출고창고는 필수입니다."); return; }
                if (!Number.isInteger(수량) || 수량 <= 0) { showError("올바른 수량을 입력하세요."); return; }
                if (looksLikeRealBl(BL)) { showError("타사 출고/기타 특이품분만 추가 가능합니다."); return; }
                results.push({
                    상품명, BL, 창고, 수량,
                    브랜드: val(".mi-brand"), 등급: val(".mi-grade"), ESTNO: val(".mi-estno"),
                    배차자: val(".mi-dispatcher"), 이동창고: val(".mi-move-wh"),
                    실중량: val(".mi-weight") ? Number(val(".mi-weight")) : null,
                    담당자: val(".mi-manager"), 매출처: val(".mi-client"),
                    수정사항: val(".mi-note"),
                    평중: val(".mi-avgweight") ? Number(val(".mi-avgweight")) : null,
                    비고: val(".mi-remark"),
                });
            }
            if (results.length === 0) { showError("최소 1건은 입력하세요."); return; }
            close(results);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 전달사항 모달 — 예약/출고 행의 "!" 버튼(2026-08-14). 보기/수정 겸용, 저장
// 누르면 새 문자열(빈 문자열이면 삭제)로 resolve, 취소/바깥클릭이면 null.
// 전달사항 팝업(2026-08-18 재설계) — 처음엔 보기 전용으로 뜨고(확인/수정),
// "수정"을 눌러야 텍스트박스 + 저장/취소가 나오는 2단계 흐름. 그냥 "!"만
// 눌러도 바로 편집 모드로 들어가던 전엔 실수로 고치기 쉬웠다는 피드백 반영.
// canEdit=false면 "수정" 버튼을 빼서 보기 전용으로(2026-08-20) — 담당자 본인이거나
// 편집자만 고칠 수 있고, 나머지는 조회만 가능.
export function showNoteModal(note, canEdit = true) {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        document.body.appendChild(overlay);

        const escapeHtml = s => String(s ?? "").replace(/</g, "&lt;");
        const close = (result) => { overlay.remove(); resolve(result); };

        const renderView = () => {
            const hasNote = !!(note && note.trim());
            overlay.innerHTML =
                `<div class="confirm-modal edit-reservation-modal">` +
                `<p class="confirm-msg">전달사항</p>` +
                `<div class="note-modal-view">${hasNote ? escapeHtml(note) : `<span class="note-modal-empty">전달사항이 없습니다.</span>`}</div>` +
                `<div class="confirm-btns">` +
                (canEdit ? `<button class="confirm-edit">수정</button>` : "") +
                `<button class="confirm-yes">확인</button>` +
                `</div></div>`;
            overlay.querySelector(".confirm-edit")?.addEventListener("click", renderEdit);
            overlay.querySelector(".confirm-yes").addEventListener("click", () => close(null));
            (overlay.querySelector(".confirm-edit") || overlay.querySelector(".confirm-yes")).focus();
        };

        const renderEdit = () => {
            overlay.innerHTML =
                `<div class="confirm-modal edit-reservation-modal">` +
                `<p class="confirm-msg">전달사항</p>` +
                `<div class="edit-reservation-form">` +
                `<textarea class="note-modal-input" maxlength="100" rows="3">${escapeHtml(note)}</textarea>` +
                `</div>` +
                `<div class="confirm-btns">` +
                `<button class="confirm-yes">저장</button>` +
                `<button class="confirm-no">취소</button>` +
                `</div></div>`;
            overlay.querySelector(".note-modal-input").focus();
            overlay.querySelector(".confirm-yes").addEventListener("click", () => {
                close(overlay.querySelector(".note-modal-input").value.trim());
            });
            overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        };

        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
        renderView();
    });
}

// 출고취소(사용완료 아님) 팝업 — 예약으로 되돌릴지, 아예 삭제할지 선택
// (2026-08-18, 삭제를 원해도 무조건 예약현황으로 되돌아가던 문제 개선).
export function showCancelOutboundModal() {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal">` +
            `<p class="confirm-msg">출고를 취소합니다.\n이 출고건을 어떻게 처리할까요?</p>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-revert">예약으로 되돌리기</button>` +
            `<button class="confirm-delete">삭제</button>` +
            `<button class="confirm-no">닫기</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-revert").addEventListener("click", () => close("revert"));
        overlay.querySelector(".confirm-delete").addEventListener("click", () => close("delete"));
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        // 되돌리기/삭제/닫기 3개 중 하나를 고르는 팝업이라 애매한 기본 동작이
        // 없음 — Enter로 저장하지 않고 Esc/드래그-안전 바깥클릭만 적용.
        wireModalOverlay(overlay, { onCancel: () => close(null) });
    });
}

// 재고장 표 "예약" 열 배지 클릭 시 뜨는 상세 팝업(2026-08-20, 아코디언에서
// 모달로 변경) — 그 상품에 걸린 예약/출고 건을 누가/얼마에/언제/어디로/몇개
// 걸었는지 조회 전용으로 보여준다. 취소 버튼 없음(여러 군데서 취소 가능하면
// 혼란스러움, 2026-08-06 결정 유지).
export function showReservationDetailModal(reservations) {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal reservation-detail-modal">` +
            `<p class="confirm-msg">예약/출고 상세</p>` +
            `<div class="reservation-detail-list">${reservationListItemsHtml(reservations)}</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">확인</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = () => { overlay.remove(); resolve(); };
        overlay.querySelector(".confirm-yes").addEventListener("click", close);
        wireModalOverlay(overlay, { onCancel: () => close(), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 확인 버튼 하나뿐인 안내 팝업(2026-08-18) — 등록완료 미체크 상태에서 출고완료를
// 누르면 뜨는 경고 등, 그냥 지나치면 안 되는 안내에 씀(토스트는 자동으로 사라져서
// 놓치기 쉬움).
export function showAlertModal(msg) {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal">` +
            `<p class="confirm-msg">${msg.replace(/\n/g, "<br>")}</p>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">확인</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = () => { overlay.remove(); resolve(); };
        overlay.querySelector(".confirm-yes").addEventListener("click", close);
        wireModalOverlay(overlay, { onCancel: () => close(), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 전략단가 엑셀 다운로드 전에 도매가/전략가 열 포함 여부를 물어보는 팝업
// (2026-08-19) — 가격 정보라 공유 상대에 따라 빼고 싶을 때가 있어서 선택 가능하게.
// 저장 누르면 {도매가: bool, 전략가: bool} 객체로 resolve, 취소/바깥클릭이면 null.
export function showPriceExportModal() {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal">` +
            `<p class="confirm-msg">엑셀에 포함할 가격 열을 선택하세요</p>` +
            `<div class="edit-reservation-form" style="justify-content:center;">` +
            `<label style="flex-direction:row; align-items:center; gap:8px;"><input type="checkbox" class="export-wholesale" checked> 도매가</label>` +
            `<label style="flex-direction:row; align-items:center; gap:8px;"><input type="checkbox" class="export-strategy" checked> 전략가</label>` +
            `</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">다운로드</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            close({
                도매가: overlay.querySelector(".export-wholesale").checked,
                전략가: overlay.querySelector(".export-strategy").checked,
            });
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 전략단가 모바일 카드용 수정 모달(2026-08-19) — 데스크톱은 더블클릭 인라인
// 수정이지만 모바일 카드는 탭으로 이 모달을 띄운다. PRICE_FIELDS 순서 그대로
// 입력칸을 생성. 저장 누르면 필드별 값 객체로 resolve, 취소/바깥클릭이면 null.
export function showEditPriceModal(row) {
    return new Promise(resolve => {
        const fieldsHtml = PRICE_FIELDS.map(f => {
            const cls = `edit-price-${f.key.replace(/\//g, "-")}`;
            const type = f.type === "date" ? "date" : (f.type === "number" ? "number" : "text");
            const val = String(row[f.key] ?? "").replace(/"/g, "&quot;");
            return `<label>${f.key}<input type="${type}" ${type === "number" ? 'step="any"' : ""} class="${cls}" value="${val}"></label>`;
        }).join("");

        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal edit-price-modal">` +
            `<p class="confirm-msg">단가표 수정</p>` +
            `<div class="edit-reservation-form">${fieldsHtml}</div>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">저장</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => {
            const result = {};
            PRICE_FIELDS.forEach(f => {
                const cls = `edit-price-${f.key.replace(/\//g, "-")}`;
                const v = overlay.querySelector(`.${cls}`).value.trim();
                result[f.key] = v === "" ? null : (f.type === "number" ? Number(v) : v);
            });
            close(result);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        wireModalOverlay(overlay, { onCancel: () => close(null), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

export function showConfirm(msg) {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal">` +
            `<p class="confirm-msg">${msg.replace(/\n/g, "<br>")}</p>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">확인</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        const close = (result) => { overlay.remove(); resolve(result); };
        overlay.querySelector(".confirm-yes").addEventListener("click", () => close(true));
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(false));
        wireModalOverlay(overlay, { onCancel: () => close(false), onSubmit: () => overlay.querySelector(".confirm-yes").click() });
    });
}

// 재고장 "수정"/"예약" 팝업 모달(2026-08-24 전체 공개) — 여러
// 행을 선택해도 하나의 팝업 안에 전부 들어간다. cardsHtml은 호출부(events.js)가
// table.js의 createUpdateCard/createHoldingCard로 미리 만들어서 넘긴다 —
// 여기서는 저장/취소 버튼과 모달 껍데기만 관리하고, 실제 저장 로직(updateData/
// holdingData 호출)은 onSave 콜백으로 위임한다(순환 import 방지 — crud.js/
// firebase.js/crud_history.js를 ui.js가 직접 끌어오지 않음).
export function showBulkEditModal(title, cardsHtml, { onSave } = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML = `
            <div class="confirm-modal bulk-edit-modal">
                <p class="confirm-msg">${title}</p>
                <div class="bulk-edit-scroll">${cardsHtml}</div>
                <div class="confirm-btns">
                    <button class="confirm-yes bulk-modal-save-btn">저장</button>
                    <button class="confirm-no bulk-modal-cancel-btn">취소</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        const close = () => { overlay.remove(); resolve(); };
        // 팝업 전체 "취소"(2026-08-24) — 개별 카드 "✕"와 달리 이건 처리 자체를
        // 그만두는 것이므로, 남아있는 선택을 재고장에서도 전부 초기화한다(실제
        // 체크박스를 클릭시켜 handleChange를 그대로 태움 — 개별 취소와 동일한 방식).
        const cancelAndClear = () => {
            document.querySelectorAll(".row-check:checked").forEach(cb => cb.click());
            close();
        };
        overlay.querySelector(".bulk-modal-cancel-btn").addEventListener("click", cancelAndClear);
        const saveBtn = overlay.querySelector(".bulk-modal-save-btn");
        saveBtn.addEventListener("click", async (e) => {
            e.target.disabled = true;
            if (onSave) await onSave(overlay);
            close();
        });
        // 바깥클릭(드래그-안전)/Esc는 close()(선택 유지, cancelAndClear의 체크
        // 해제까지는 안 함 — 기존 바깥클릭 동작과 동일), Enter는 저장(2026-09-04
        // "재고장 메인 수정/예약도 엔터로 저장" 요청 — 이제 모든 호출부 공통 적용).
        wireModalOverlay(overlay, {
            onCancel: close,
            onSubmit: () => { if (!saveBtn.disabled) saveBtn.click(); },
        });
        // 카드별 "✕" — 팝업 열어둔 채로 그 상품만 이번 처리 대상에서 뺀다(2026-08-24).
        // 뒤에 깔린 표의 체크박스를 실제로 클릭해서(state.selectedItems.delete를
        // 직접 하지 않고) 앱이 원래 쓰는 선택 해제 경로(handleChange)를 그대로
        // 태워 상태 일관성을 유지한다 — 그래야 체크박스 표시/선택 카운트 등도 같이 맞음.
        overlay.addEventListener("click", (e) => {
            const removeBtn = e.target.closest(".bulk-edit-card-remove");
            if (!removeBtn) return;
            const id = removeBtn.dataset.id;
            const checkbox = document.querySelector(`.row-check[data-id="${CSS.escape(id)}"]`);
            if (checkbox?.checked) checkbox.click();
            removeBtn.closest(".bulk-edit-card")?.remove();
            const remaining = overlay.querySelectorAll(".bulk-edit-card[data-id]").length;
            if (remaining === 0) { close(); return; }
            const msg = overlay.querySelector(".confirm-msg");
            if (msg) msg.textContent = msg.textContent.replace(/\d+(?=건\))/, remaining);
        });
    });
}
