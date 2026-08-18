import { state } from "./state.js";
import { renderTable, updateSortHeaders, renderBulkActionBar, renderChangesTab, getChangesTabRows, createReservationListRow, renderReservationsTab, renderSalesTab, clientPrefix, parseUnitPrice, parseWeight, buildClientWithDetails, outboundInsertRowHtml } from "./table.js";
import { renderSelectData, renderInsert, createInsertRow } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData, insertData, updateData, deleteItem } from "./crud.js";
import { getReservationsByPk, cancelReservation, useReservation, updateReservation, updateOutbound, cancelOutbound, createOutbound, registerOutboundFromReservation, toggleOutboundComplete, toggleOutboundRegister } from "./firestoreService.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";
import { undoLastAction, pushUndo } from "./crud_history.js";
import { fetchAllData } from "./firebase.js";
import { showToast, showError, showConfirm, showEditReservationModal, showRegisterOutboundModal, showNoteModal, showCancelOutboundModal, showAlertModal } from "./ui.js";
import { getStoredUser } from "./login.js";
import { apiLogActivity } from "./api.js";

// 예약현황/타창고매출현황 액션(취소/완료/변경/토글 등) 이후 공용 새로고침(2026-08-19) —
// renderSalesTab()이 renderReservationsTab()에서 분리되며(2026-08-18) 각 액션
// 핸들러가 여전히 renderReservationsTab()만 불러서, 타창고매출현황 탭에서 액션을
// 눌러도 그 탭(.sales-container)은 안 보이던 renderReservationsTab()이 자기 컨테이너
// 안 보인다고 조용히 스킵해 화면이 그대로였던 버그 수정. 두 render 함수 다 자기
// 탭 컨테이너가 안 보이면 알아서 스킵하니 항상 같이 불러도 안전하다.
async function refreshReservationViews() {
    await renderReservationsTab();
    await renderSalesTab();
}

// activity_log(2026-08-18, 예약현황/타창고매출현황 연결) — crud.js의 _logActivity와
// 같은 목적, 재고장 쪽 테이블(inventory/azy_inventory) 구분과 달리 여기는 근원 창고가
// main/azy 어느 쪽이든 예약/출고 자체는 한 테이블(holding_records류/outbound)이라
// table_name을 "reservation"/"outbound"로만 단순화한다. 로그인 안 돼 있으면(user_id
// 없음) 서버가 거절하니 호출 자체를 스킵.
function _logActivity(tableName, recordId, action, before, after, summary = "") {
    const user = getStoredUser();
    if (!user?.id) return;
    apiLogActivity({
        user_id: user.id, user_name: user.이름 || "",
        action, table_name: tableName, record_id: String(recordId),
        before: before ?? null, after: after ?? null, summary,
    });
}

// 재고장 표와 배타적으로 토글되는 탭들(업데이트/예약현황/타창고매출현황/전략단가,
// 2026-08-18) — 하나 열면 나머지는 다 닫힌다. 열릴 때만 render를 부르므로(이미
// 열려있으면 콘텐츠 그대로 두고 숨기기만 함) 매번 다시 불러오지 않는다.
const TAB_CONTAINERS = [".changes-container", ".reservations-container", ".sales-container", ".price-container"];
const TAB_BUTTONS = [".changes-tab-btn", ".reservations-tab-btn", ".sales-tab-btn", ".price-tab-btn"];

function switchTab(btnClass, containerSelector, render) {
    const tableContainer = document.querySelector(".table-container");
    const targetContainer = document.querySelector(containerSelector);
    if (!tableContainer || !targetContainer) return;
    const opening = targetContainer.style.display === "none";

    TAB_CONTAINERS.forEach(sel => { const el = document.querySelector(sel); if (el) el.style.display = "none"; });
    TAB_BUTTONS.forEach(sel => document.querySelector(sel)?.classList.remove("active"));
    tableContainer.style.display = opening ? "none" : "";

    if (opening) {
        targetContainer.style.display = "";
        document.querySelector(`.${btnClass}`)?.classList.add("active");
        render?.();
    }
}

// rows(배열의 배열, 헤더 포함)를 CSV(엑셀 호환)로 내려받기 — 업데이트 탭/메인 테이블
// 다운로드가 공유하는 헬퍼(2026-08-06).
function downloadCsv(filenamePrefix, headers, rows) {
    const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [headers.map(esc).join(","), ...rows.map(r => r.map(esc).join(","))];
    const csv = "﻿" + lines.join("\r\n"); // BOM — 엑셀에서 한글 깨짐 방지
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const today = new Date();
    const pad = n => String(n).padStart(2, "0");
    a.href = url;
    a.download = `${filenamePrefix}_${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

export function bindEvents() {

    // 날짜 입력창(<input type="date">)은 기본적으로 달력 아이콘을 눌러야만 날짜
    // 선택기가 열려서 불편함 — 박스 어디를 클릭해도 열리게 함(2026-08-13).
    // showPicker() 미지원 브라우저에서는 그냥 원래대로 아이콘 클릭만 동작(자동 무시).
    document.addEventListener("click", (e) => {
        if (e.target.matches('input[type="date"]') && typeof e.target.showPicker === "function") {
            e.target.showPicker();
        }
    });

    // sales.html "추가" 입력행 — 재고장(메인 표) 행 하나를 통째로 복사해서
    // 붙여넣으면 탭으로 구분된 여러 값이 한 번에 들어오는데, 클릭한 칸 하나에만
    // 박히지 않고 재고장 열 순서에 맞춰 각 칸에 자동으로 나눠 들어가게 함
    // (2026-08-14). 재고장 열 순서(선택 제외): 상품명,브랜드,등급,ESTNO,BL,창고,
    // 재고,예약,가용,유통기한,평균,비고 — outbound엔 없는 열(예약/가용/유통기한/
    // 평균/비고)은 그냥 건너뛴다. 붙여넣은 칸이 이 열 목록 중 어디인지로 시작
    // 위치를 찾아서, 그 뒤로 순서대로 채운다.
    const INVENTORY_COL_ORDER = ["상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "재고", "예약", "가용", "유통기한", "평균", "비고"];
    const OUTBOUND_FIELD_BY_INVENTORY_COL = {
        "상품명": "ob-in-name", "브랜드": "ob-in-brand", "등급": "ob-in-grade",
        "ESTNO": "ob-in-estno", "BL": "ob-in-bl", "창고": "ob-in-wh", "재고": "ob-in-qty",
    };
    document.addEventListener("paste", (e) => {
        const target = e.target;
        const row = target.closest?.(".outbound-insert-row");
        if (!row || !target.matches("input")) return;
        const text = (e.clipboardData || window.clipboardData)?.getData("text") || "";
        const values = text.split(/\r\n|\n/)[0].split("\t");
        if (values.length < 2) return; // 값이 하나면 기본 붙여넣기 그대로 둠

        const startCol = INVENTORY_COL_ORDER.findIndex(
            col => OUTBOUND_FIELD_BY_INVENTORY_COL[col] && target.classList.contains(OUTBOUND_FIELD_BY_INVENTORY_COL[col])
        );
        if (startCol === -1) return; // 매핑 안 되는 칸(거래처명/단가/중량/담당자/출고일)은 기본 동작

        e.preventDefault();
        values.forEach((val, i) => {
            const col = INVENTORY_COL_ORDER[startCol + i];
            const fieldClass = col && OUTBOUND_FIELD_BY_INVENTORY_COL[col];
            if (!fieldClass) return; // 매핑 없는 열(예약/가용/유통기한/평균/비고)은 건너뜀
            const input = row.querySelector(`.${fieldClass}`);
            if (input) input.value = val.trim();
        });
    });

    // 화면 맨 위(고정 헤더) 빈 공간 클릭 시 테이블 스크롤 맨 위로 — 버튼/입력 등
    // 실제 컨트롤을 클릭한 경우는 그쪽 핸들러가 처리하니 헤더 배경 자체를 클릭했을 때만 동작
    const stickyHeader = document.querySelector(".sticky-header");
    const tableContainer = document.querySelector(".table-container");
    if (stickyHeader && tableContainer) {
        stickyHeader.addEventListener("click", (e) => {
            if (e.target !== stickyHeader) return;
            tableContainer.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    // 상단 고정 영역(툴바+패널) 숨기기/보이기 토글 — 화면이 좁을 때 표 영역을
    // 더 넓게 쓰고 싶을 때용. 선택 상태는 새로고침해도 유지되게 저장.
    const STICKY_HEADER_HIDDEN_KEY = "sticky_header_hidden";
    const toggleStickyHeaderBtn = document.getElementById("toggle-sticky-header-btn");
    if (stickyHeader && toggleStickyHeaderBtn) {
        const applyHidden = (hidden) => {
            stickyHeader.classList.toggle("is-hidden", hidden);
            toggleStickyHeaderBtn.classList.toggle("is-collapsed", hidden);
            toggleStickyHeaderBtn.title = hidden ? "상단 고정 영역 보이기" : "상단 고정 영역 숨기기";
        };
        applyHidden(localStorage.getItem(STICKY_HEADER_HIDDEN_KEY) === "1");
        toggleStickyHeaderBtn.addEventListener("click", () => {
            const hidden = !stickyHeader.classList.contains("is-hidden");
            applyHidden(hidden);
            localStorage.setItem(STICKY_HEADER_HIDDEN_KEY, hidden ? "1" : "0");
        });
    }

    // 모바일에서 "PC" 버튼으로 데스크톱 화면 강제 보기 — 뷰포트 메타를 넓게 바꿔서
    // 모바일 미디어쿼리 자체가 안 걸리게 만드는 방식(실제 "데스크톱 사이트 요청"과 동일 원리).
    // 선택 상태는 새로고침해도 유지되게 저장.
    const FORCE_DESKTOP_KEY = "force_desktop_view";
    const DESKTOP_VIEWPORT = "width=1280";
    const MOBILE_VIEWPORT = "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no";
    const toggleDesktopViewBtn = document.getElementById("toggle-desktop-view-btn");
    const viewportMeta = document.querySelector('meta[name="viewport"]');
    if (toggleDesktopViewBtn && viewportMeta) {
        const applyForceDesktop = (forced) => {
            document.body.classList.toggle("force-desktop-view", forced);
            viewportMeta.setAttribute("content", forced ? DESKTOP_VIEWPORT : MOBILE_VIEWPORT);
            toggleDesktopViewBtn.textContent = forced ? "모바일" : "PC";
            toggleDesktopViewBtn.title = forced ? "모바일 화면으로 보기" : "PC 화면으로 보기";
        };
        applyForceDesktop(localStorage.getItem(FORCE_DESKTOP_KEY) === "1");
        toggleDesktopViewBtn.addEventListener("click", () => {
            const forced = !document.body.classList.contains("force-desktop-view");
            applyForceDesktop(forced);
            localStorage.setItem(FORCE_DESKTOP_KEY, forced ? "1" : "0");
        });
    }

    // 출고일·홀딩 hover 카드
    const hoverCard = document.createElement("div");
    hoverCard.id = "hover-info-card";
    document.body.appendChild(hoverCard);

    let _hoveredTr = null;
    const tableEl = document.querySelector(".table-wrap table");
    if (tableEl) {
        tableEl.addEventListener("mouseover", async (e) => {
            const tr = e.target.closest("tbody tr");
            if (tr === _hoveredTr) return;
            _hoveredTr = tr;
            if (!tr) { hoverCard.style.display = "none"; return; }

            const 출고일 = tr.dataset.출고일 || "";
            const 홀딩   = tr.dataset.홀딩   || "";
            const pk     = tr.dataset.pk || "";
            const hasReservation = Number(tr.dataset.예약수량 || 0) > 0;

            if (!출고일 && !홀딩 && !hasReservation) { hoverCard.style.display = "none"; return; }

            // 예약이 있으면 실제 예약 레코드(담당자/출고일자/비고)를 가져와서 보여준다 —
            // 행 자체의 홀딩/출고일 필드는 예약과 분리된 이후로는 안 채워지는 옛 필드라
            // 여기서 실제 예약 정보를 따로 조회해야 함(2026-08-06).
            let reservationsHtml = "";
            if (hasReservation && pk) {
                try {
                    const reservations = await getReservationsByPk(pk);
                    if (tr !== _hoveredTr) return; // 그 사이 다른 행으로 넘어갔으면 무시(오래된 응답)
                    reservationsHtml = reservations.map(r => `
                        <div class="hc-reservation">
                            <div><span class="hc-label">담당자</span>${r.홀딩 || "(미지정)"}</div>
                            <div><span class="hc-label">출고일자</span>${r.출고일 || "-"}</div>
                            <div><span class="hc-label">비고</span>${r.메모 || "-"}</div>
                        </div>
                    `).join("");
                } catch {
                    reservationsHtml = "";
                }
            }
            if (tr !== _hoveredTr) return;

            hoverCard.innerHTML =
                (출고일 ? `<div><span class="hc-label">출고일</span>${출고일}</div>` : "") +
                (홀딩   ? `<div><span class="hc-label">예약자</span>${홀딩}</div>`   : "") +
                reservationsHtml;

            if (!hoverCard.innerHTML) { hoverCard.style.display = "none"; return; }

            const rect = tr.getBoundingClientRect();
            hoverCard.style.top   = (rect.bottom + 4) + "px";
            hoverCard.style.left  = "auto";
            hoverCard.style.right = (window.innerWidth - rect.right) + "px";
            hoverCard.style.display = "block";
        });
        tableEl.addEventListener("mouseleave", () => {
            _hoveredTr = null;
            hoverCard.style.display = "none";
        });

        // 추가/수정/홀딩 입력행이 뜨거나 사라질 때마다 우하단 전체 처리 바 갱신
        new MutationObserver(renderBulkActionBar).observe(tableEl, { childList: true, subtree: true });
    }

    // 드래그 감지 (드래그 중 행 체크 방지)
    let _dragStartX = 0, _dragStartY = 0, _isDragging = false;
    document.addEventListener("mousedown", (e) => {
        _dragStartX = e.clientX;
        _dragStartY = e.clientY;
        _isDragging = false;
    });
    document.addEventListener("mousemove", (e) => {
        if (Math.abs(e.clientX - _dragStartX) > 5 || Math.abs(e.clientY - _dragStartY) > 5) {
            _isDragging = true;
        }
    });

    ["상품명", "브랜드", "등급", "ESTNO", "재고", "예약수량", "가용재고", "BL", "창고", "유통기한", "평중", "메모"].forEach(key => {
        document.querySelector(`th[data-key="${key}"]`)?.addEventListener("click", () => {
            const idx = state.sortColumns.findIndex(s => s.key === key);
            if (idx === -1) {
                state.sortColumns.push({ key, dir: 1 });       // 없으면 추가(오름차)
            } else if (state.sortColumns[idx].dir === 1) {
                state.sortColumns[idx].dir = 2;                 // 오름차 → 내림차
            } else {
                state.sortColumns.splice(idx, 1);               // 내림차 → 제거
            }
            renderTable();
        });
    });

    // 검색/필터 툴바는 재고장 표 + 예약현황 + 타창고매출현황 탭이 다 같이 쓴다
    // (2026-08-18, sales.html이 탭으로 통합되며 페이지 구분 불필요 — 각 render
    // 함수가 자기 탭 컨테이너가 안 보이면 알아서 스킵).
    const refreshFilteredViews = () => {
        renderTable();
        refreshReservationViews();
    };

    let searchTimer = null;
    dom.searchInput?.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(refreshFilteredViews, 200);
    });

    let searchTimer2 = null;
    dom.searchInput2?.addEventListener("input", () => {
        clearTimeout(searchTimer2);
        searchTimer2 = setTimeout(refreshFilteredViews, 200);
    });

    let filterTimer = null;
    ["show-warehouse", "show-product-name", "show-brand", "show-state"].forEach(cls => {
        document.querySelector(`.${cls}`)?.addEventListener("change", () => {
            clearTimeout(filterTimer);
            filterTimer = setTimeout(refreshFilteredViews, 100);
        });
    });

    document.addEventListener("change", (e) => {
        if (e.target.classList.contains("row-check")) handleChange(e);
        if (e.target.classList.contains("outbound-register-check")) {
            const id = e.target.dataset.id;
            const checkbox = e.target;
            checkbox.disabled = true;
            toggleOutboundRegister(id)
                .then(() => {
                    pushUndo({ type: "outbound-toggle-register", id });
                    _logActivity("outbound", id, "등록완료토글", null, null, "등록완료 체크 토글");
                    refreshReservationViews();
                })
                .catch((err) => {
                    checkbox.checked = !checkbox.checked;
                    checkbox.disabled = false;
                    showError(err.message || "처리에 실패했습니다.");
                });
        }
        if (e.target.id === "reservations-filter") {
            state.reservationsFilter = e.target.value;
            renderReservationsTab();
        }
        if (e.target.id === "reservations-date-filter") {
            state.reservationsDateFilter = e.target.value;
            renderReservationsTab();
        }
        if (e.target.id === "sales-date-filter") {
            state.salesDateFilter = e.target.value;
            renderSalesTab();
        }
    });

    document.addEventListener("input", (e) => {
        if (!e.target.classList.contains("hold-qty")) return;
        const total = calculateTotal();
        const totalBox = document.querySelector("#total-box");
        if (totalBox) totalBox.innerText = `총 ${total} 박스`;
    });

    document.addEventListener("click", handleClick);

    // 더블클릭으로 행 선택
    document.addEventListener("dblclick", (e) => {
        if (e.target.classList.contains("row-check")) return;

        // 타창고매출현황 — 비고 칸 더블클릭하면 그 자리에서 바로 수정(2026-08-19,
        // 매번 "출고변경" 모달을 열지 않아도 되게). 이미 입력창으로 바뀐 상태면
        // 다시 더블클릭해도 무시(inline input 안에서의 더블클릭은 텍스트 선택용).
        const remarkCell = e.target.closest(".sales-remark-cell");
        if (remarkCell) {
            if (remarkCell.querySelector("input")) return;
            const id = remarkCell.dataset.id;
            const original = remarkCell.dataset.remark || "";
            remarkCell.innerHTML = `<input type="text" class="sales-remark-input" value="${original.replace(/"/g, "&quot;")}">`;
            const input = remarkCell.querySelector("input");
            input.focus();
            input.select();

            let done = false;
            const finish = async (save) => {
                if (done) return;
                done = true;
                const newValue = input.value.trim();
                if (save && newValue !== original) {
                    try {
                        await updateOutbound(id, { 비고: newValue });
                        _logActivity("outbound", id, "수정", { 비고: original }, { 비고: newValue }, "비고 변경");
                        showToast("✓ 비고 저장됨");
                    } catch (err) {
                        showError(err.message || "저장에 실패했습니다.");
                    }
                }
                renderSalesTab();
            };
            input.addEventListener("blur", () => finish(true));
            input.addEventListener("keydown", (ke) => {
                if (ke.key === "Enter") { ke.preventDefault(); input.blur(); }
                if (ke.key === "Escape") { ke.preventDefault(); finish(false); }
            });
            return;
        }

        const target = e.target.closest("tr") || e.target.closest(".mobile-card");
        if (!target) return;

        const checkbox = target.querySelector(".row-check");
        if (!checkbox) return;
        if (checkbox.disabled) return; // 이고(moving) 행 등 선택 금지된 행은 더블클릭으로도 선택 못 하게

        const id = checkbox.dataset.id;
        const item = state.allData.find(d => d.id === id);
        if (!item) return;

        const nowChecked = !state.selectedItems.has(id);
        if (nowChecked) {
            addSelectedItem(state, id, item);
        } else {
            state.selectedItems.delete(id);
            if (state.selectedItems.size === 0) state.crudData = null;
        }

        // ① 체크박스·행 클래스만 토글
        checkbox.checked = nowChecked;
        if (target.tagName === "TR") {
            target.classList.toggle("selected-row", nowChecked);
        } else {
            target.classList.toggle("mobile-selected", nowChecked);
        }

        if (state.selectedItems.size === 0) {
            dom.container?.classList.remove("active");
            if (dom.sideBox) dom.sideBox.innerHTML = "";
            window.getSelection()?.removeAllRanges();
            return;
        }

        switch (state.crudData) {
            case "update":
            case "holding":
                renderTable();
                break;
            default:
                renderSelectData();
        }

        window.getSelection()?.removeAllRanges();
    });
}

function renderAll() {
    renderTable();
    renderSelectData();
}

// 저장된 유통기한은 "2028.01.04" 형식(점 구분) — <input type="date">가 내놓는 "YYYY-MM-DD"를 다시 점 형식으로
function toDotDate(v) {
    return v ? v.replace(/-/g, ".") : "";
}

function handleChange(e) {
    const id = e.target.dataset.id;
    const item = state.allData.find(d => d.id === id);
    if (!item) return;

    const checked = e.target.checked;
    if (checked) {
        addSelectedItem(state, id, item);
    } else {
        state.selectedItems.delete(id);
    }

    // ① 해당 행/카드 클래스만 토글 (전체 테이블 재렌더 안 함)
    e.target.closest("tr")?.classList.toggle("selected-row", checked);
    document.querySelector(`.mobile-card[data-id="${id}"]`)?.classList.toggle("mobile-selected", checked);

    if (state.selectedItems.size === 0) {
        state.crudData = null;
        dom.container?.classList.remove("active");
        if (dom.sideBox) dom.sideBox.innerHTML = "";
        return;
    }

    // ② 패널 업데이트 (중복 renderSelectData 제거)
    switch (state.crudData) {
        case "update":
        case "holding":
            renderTable();
            break;
        default:
            renderSelectData();
    }
}

async function handleClick(e) {
    // 예약 수량 클릭 — 아코디언으로 펼쳐서 거래처별 예약 목록 표시 (조회 전용, 취소 버튼 없음 —
    // 취소가 여러 군데서 가능하면 혼란스러워질 수 있어 2026-08-06 제거)
    if (e.target.classList.contains("view-reservations-btn")) {
        const pk = e.target.dataset.pk;
        const tr = e.target.closest("tr");
        const existing = tr?.nextElementSibling;
        if (existing?.classList.contains("reservation-list-row")) {
            existing.remove();
            return;
        }
        document.querySelectorAll("tr.reservation-list-row").forEach(r => r.remove());
        const reservations = await getReservationsByPk(pk);
        tr?.insertAdjacentHTML("afterend", createReservationListRow(pk, reservations));
        return;
    }

    // 전체 선택 (현재 필터된 행만)
    if (e.target.classList.contains("select-all")) {
        const visible = state.filteredData.length > 0 ? state.filteredData : state.allData;
        const allChecked = visible.every(item => state.selectedItems.has(item.id));
        state.selectedItems.clear();
        if (!allChecked) {
            visible.forEach(item => addSelectedItem(state, item.id, item));
        }
        renderAll();
        renderSelectData();
        return;
    }

    // 필터 셀렉트 클릭 (change 이벤트 보완용)
    if (
        e.target.classList.contains("show-warehouse") ||
        e.target.classList.contains("show-product-name") ||
        e.target.classList.contains("show-brand") ||
        e.target.classList.contains("show-state")
    ) {
        setTimeout(() => renderTable(), 0);
        return;
    }

    // 추가 버튼 — 타창고매출현황 탭에서는 팝업 대신 엑셀처럼 표 맨 위에 입력행을
    // 띄운다(2026-08-14). 이미 떠 있으면 토글로 닫는다.
    if (e.target.classList.contains("insert-btn") && document.querySelector(".sales-container")?.style.display === "") {
        const body = document.getElementById("outbound-insert-rows");
        if (!body) return;
        body.innerHTML = body.children.length > 0 ? "" : outboundInsertRowHtml();
        return;
    }

    // sales.html 입력행 — 저장(→ outbound 생성). 출고일 비우면 서버가 오늘로
    // 채우고, 출고일에 따라 outbound/예약 테이블 중 맞는 곳으로 들어간다.
    if (e.target.classList.contains("save-outbound-insert-btn")) {
        const row = e.target.closest("tr");
        const val = sel => row.querySelector(sel)?.value.trim() ?? "";
        const 상품명 = val(".ob-in-name"), BL = val(".ob-in-bl"), 창고 = val(".ob-in-wh");
        const 수량 = Number(val(".ob-in-qty"));
        if (!상품명 || !BL || !창고) { showError("상품명/BL/창고는 필수입니다."); return; }
        if (!Number.isInteger(수량) || 수량 <= 0) { showError("올바른 수량을 입력하세요."); return; }
        try {
            const newFields = {
                상품명, BL, 창고, 수량,
                브랜드: val(".ob-in-brand"), 등급: val(".ob-in-grade"), ESTNO: val(".ob-in-estno"),
                담당자: val(".ob-in-manager"), 출고일: val(".ob-in-date"),
                거래처: buildClientWithDetails(val(".ob-in-client"), val(".ob-in-price"), val(".ob-in-weight")),
                비고: val(".ob-in-remark"),
            };
            const res = await createOutbound(newFields);
            if (res?.id) pushUndo({ type: "outbound-created", id: res.id });
            if (res?.id) _logActivity("outbound", res.id, "삽입", null, newFields, `${상품명} ${수량}개 출고 추가`);
            showToast("✓ 추가됨");
            renderSalesTab();
        } catch (err) {
            showError(err.message || "추가에 실패했습니다.");
        }
        return;
    }

    // sales.html 입력행 — 취소(입력행만 지움)
    if (e.target.classList.contains("cancel-outbound-insert-btn")) {
        document.getElementById("outbound-insert-rows").innerHTML = "";
        return;
    }

    // 추가 버튼 — 테이블 맨 위에 입력행을 띄우거나(없으면) 닫는다(있으면). 선택/수정/홀딩 패널과는 무관하게 독립 동작.
    if (e.target.classList.contains("insert-btn")) {
        if (dom.insertRowsBody && dom.insertRowsBody.children.length > 0) {
            dom.insertRowsBody.innerHTML = "";
            return;
        }
        renderInsert();
        return;
    }

    // 추가 입력행 취소
    const removeBtn = e.target.closest(".remove-insert-btn, .card-close-btn");
    if (removeBtn && removeBtn.closest(".insert-card")) {
        removeBtn.closest(".insert-card").remove();
        return;
    }

    // 추가 입력행 하나 더 늘리기 (여러 상품 연속 입력)
    if (e.target.classList.contains("add-insert-row-btn")) {
        e.target.closest(".insert-card")?.insertAdjacentHTML("afterend", createInsertRow());
        return;
    }

    // 수정 버튼 — 선택한 행을 테이블 안에서 바로 편집 가능하게 전환(다시 누르면 해제)
    if (e.target.classList.contains("update-btn")) {
        if (state.selectedItems.size === 0) { showError("수정할 상품을 선택하세요."); return; }
        state.crudData = state.crudData === "update" ? null : "update";
        renderTable();
        return;
    }

    // 홀딩 버튼 — 선택한 행 밑에 홀딩 입력행을 추가(다시 누르면 해제)
    if (e.target.classList.contains("holding-btn")) {
        if (state.selectedItems.size === 0) { showError("예약할 상품을 선택하세요."); return; }
        state.crudData = state.crudData === "holding" ? null : "holding";
        renderTable();
        return;
    }

    // 업데이트/예약현황/타창고매출현황/전략단가 탭 — 재고장 표와 서로 배타적으로
    // 토글(2026-08-18, sales.html·price.html을 별도 페이지 대신 탭으로 통합하면서
    // 탭 개수가 2→4로 늘어 페어별 토글 대신 공용 switchTab으로 정리).
    if (e.target.classList.contains("changes-tab-btn")) { switchTab("changes-tab-btn", ".changes-container", renderChangesTab); return; }
    if (e.target.classList.contains("reservations-tab-btn")) { switchTab("reservations-tab-btn", ".reservations-container", renderReservationsTab); return; }
    if (e.target.classList.contains("sales-tab-btn")) { switchTab("sales-tab-btn", ".sales-container", renderSalesTab); return; }
    if (e.target.classList.contains("price-tab-btn")) { switchTab("price-tab-btn", ".price-container", null); return; }

    // 예약 현황 탭 — 출고일 필터 해제
    if (e.target.classList.contains("reservations-date-filter-clear")) {
        state.reservationsDateFilter = "";
        renderReservationsTab();
        return;
    }

    // 타창고매출현황 탭 — 출고일 필터 해제(오늘로 복귀)
    if (e.target.classList.contains("sales-date-filter-clear")) {
        state.salesDateFilter = "";
        renderSalesTab();
        return;
    }

    // 예약 현황 탭 — 예약변경(수량/출고일/거래처를 한 모달에서 같이 수정, 2026-08-14).
    // sales.html(data-sales="1")에서는 거래처 대신 거래처명+단가+중량으로 나눠 받고,
    // 저장 시 "거래처명 단가원 중량kg" 형태로 다시 합쳐서 거래처 필드에 저장한다.
    if (e.target.classList.contains("edit-reservation-btn")) {
        const id = e.target.dataset.id;
        const showPrice = e.target.dataset.sales === "1";
        const rawClient = e.target.dataset.client || "";

        const current = {
            수량: Number(e.target.dataset.qty || 0),
            출고일: e.target.dataset.release || "",
            거래처: rawClient,
            거래처명: clientPrefix(rawClient),
            단가: parseUnitPrice(rawClient) ?? "",
            중량: parseWeight(rawClient) ?? "",
            비고: e.target.dataset.remark || "",
        };
        const result = await showEditReservationModal(current, { showPrice });
        if (!result) return;
        if (!Number.isInteger(result.수량) || result.수량 <= 0) { showError("올바른 수량을 입력하세요."); return; }

        const newClient = showPrice ? buildClientWithDetails(result.거래처명, result.단가, result.중량) : result.거래처;

        const fields = {};
        const prev = {};
        if (result.수량 !== current.수량) { fields.수량 = result.수량; prev.수량 = current.수량; }
        if (result.출고일 !== current.출고일) { fields.출고일 = result.출고일; prev.출고일 = current.출고일; }
        if (newClient !== rawClient) { fields.거래처 = newClient; prev.거래처 = rawClient; }
        if (showPrice && result.비고 !== current.비고) { fields.비고 = result.비고; prev.비고 = current.비고; }
        if (Object.keys(fields).length === 0) return;

        // showPrice(=sales.html)면 outbound 항목 — 출고일을 오늘이 아닌 날짜로
        // 바꾸면 서버가 자동으로 예약 테이블로 다시 옮긴다(update_outbound 안에서 처리).
        try {
            if (showPrice) await updateOutbound(id, fields); else await updateReservation(id, fields);
            pushUndo({ type: showPrice ? "outbound-fields" : "reservation-fields", id, prev });
            _logActivity(showPrice ? "outbound" : "reservation", id, "수정", prev, fields, `${Object.keys(fields).join(", ")} 변경`);
            showToast("✓ 변경됨");
            refreshReservationViews();
            fetchAllData();
        } catch (err) {
            const msg = err.message || "변경에 실패했습니다.";
            // 예약 수량 초과 등 놓치면 안 되는 안내는 토스트(자동으로 사라짐) 대신
            // 팝업으로(2026-08-18, "예약보다 많이 출고 늘리면 알려달라"는 요청).
            if (showPrice && msg.includes("예약 수량")) await showAlertModal(msg); else showError(msg);
        }
        return;
    }

    // 예약 현황 탭 — 사용완료(입력한 수량만큼 수량 차감, 전량이면 종료 처리).
    // sales.html(data-sales="1")의 "출고완료"는 다른 동작 — outbound.status를
    // ACTIVE↔COMPLETED로 토글만 한다(수량 변경 없음). COMPLETED면 회색 배경 +
    // 맨 뒤 정렬 + 출고변경/출고취소 버튼 숨김, 다시 누르면 원상복구(2026-08-14).
    if (e.target.classList.contains("use-reservation-btn")) {
        const id = e.target.dataset.id;
        const isOutbound = e.target.dataset.sales === "1";
        if (isOutbound) {
            if (e.target.dataset.needsRegister === "1") {
                await showAlertModal("등록완료 체크 후 출고완료할 수 있습니다.\n출고 등록 여부를 확인해주세요.");
                return;
            }
            try {
                await toggleOutboundComplete(id);
                pushUndo({ type: "outbound-toggle-complete", id });
                _logActivity("outbound", id, "출고완료토글", null, null, "출고완료 상태 토글");
                renderSalesTab();
            } catch (err) {
                showError(err.message || "처리에 실패했습니다.");
            }
            return;
        }
        const maxQty = Number(e.target.dataset.qty || 0);
        const input = prompt(`사용 완료 수량을 입력하세요 (수량: ${maxQty})`, String(maxQty));
        if (input === null) return;
        const qty = Number(input);
        if (!Number.isInteger(qty) || qty <= 0) { showError("올바른 수량을 입력하세요."); return; }
        try {
            await useReservation(id, qty);
            pushUndo({ type: "reservation-used", id, prevQty: maxQty, wasFullUse: qty === maxQty });
            _logActivity("reservation", id, "사용완료", { 수량: maxQty }, { 사용수량: qty, 전량: qty === maxQty }, `${qty}개 사용완료`);
            showToast("✓ 사용 완료 처리됨");
            renderReservationsTab();
            fetchAllData();
        } catch (err) {
            showError(err.message || "처리에 실패했습니다.");
        }
        return;
    }

    // 예약 현황 탭 — 홀딩취소(수량 전체 취소). sales.html은 outbound 취소 —
    // 예약으로 되돌릴지 아예 삭제할지 선택 팝업을 띄운다(2026-08-18).
    if (e.target.classList.contains("cancel-reservation-btn")) {
        const id = e.target.dataset.id;
        const isOutbound = e.target.dataset.sales === "1";
        let deleteIt = false;
        if (isOutbound) {
            const choice = await showCancelOutboundModal();
            if (!choice) return;
            deleteIt = choice === "delete";
        } else {
            if (!await showConfirm("이 항목을 취소합니다.\n계속하시겠습니까?")) return;
        }
        // 되돌리기용 스냅샷 — 취소 직전에 미리 떠 있는 행 데이터에서 떼어둔다
        // (취소 후엔 목록에서 사라져서 다시 조회해도 못 찾음).
        const snap = state.filteredReservations.find(row => row.id === id);
        const product = snap ? {
            상품명: snap.상품명, 브랜드: snap.브랜드, 등급: snap.등급, ESTNO: snap.ESTNO,
            BL: snap.BL, 창고: snap.창고, 수량: snap.수량, 거래처: snap.거래처,
            담당자: snap.담당자, 출고일: snap.출고일,
        } : null;
        try {
            if (isOutbound) await cancelOutbound(id, deleteIt); else await cancelReservation(id);
            if (product) pushUndo({ type: isOutbound ? "outbound-cancelled" : "reservation-cancelled", product });
            _logActivity(
                isOutbound ? "outbound" : "reservation", id,
                isOutbound ? (deleteIt ? "출고삭제" : "출고취소") : "예약취소",
                product, null,
                isOutbound ? (deleteIt ? "삭제로 취소" : "예약으로 되돌림") : "예약 취소",
            );
            showToast("✓ 취소됨");
            refreshReservationViews();
            fetchAllData();
        } catch (err) {
            showError(err.message || "취소에 실패했습니다.");
        }
        return;
    }

    // 예약 현황 탭 — 출고등록(예약 수량 중 일부/전체를 outbound로 등록, 2026-08-14).
    if (e.target.classList.contains("register-outbound-btn")) {
        const id = e.target.dataset.id;
        const maxQty = Number(e.target.dataset.qty || 0);
        const result = await showRegisterOutboundModal({ 수량: maxQty });
        if (!result) return;
        try {
            const res = await registerOutboundFromReservation(id, result);
            if (res?.outbound_id) pushUndo({ type: "outbound-registered", outboundId: res.outbound_id });
            _logActivity("reservation", id, "출고등록", { 수량: maxQty }, { ...result, outboundId: res?.outbound_id }, `${result.수량}개 출고등록`);
            showToast("✓ 출고등록됨");
            renderReservationsTab();
            fetchAllData();
        } catch (err) {
            showError(err.message || "출고등록에 실패했습니다.");
        }
        return;
    }

    // 예약/출고 현황 — 전달사항 보기/수정(2026-08-14, "!" 버튼).
    if (e.target.classList.contains("reservation-note-btn")) {
        const id = e.target.dataset.id;
        const isOutbound = e.target.dataset.sales === "1";
        const current = e.target.dataset.note || "";
        const result = await showNoteModal(current);
        if (result === null || result === current) return;
        try {
            if (isOutbound) await updateOutbound(id, { 전달사항: result }); else await updateReservation(id, { 전달사항: result });
            pushUndo({ type: isOutbound ? "outbound-note" : "reservation-note", id, prevNote: current });
            _logActivity(isOutbound ? "outbound" : "reservation", id, "전달사항수정", { 전달사항: current }, { 전달사항: result });
            showToast("✓ 전달사항 저장됨");
            refreshReservationViews();
        } catch (err) {
            showError(err.message || "저장에 실패했습니다.");
        }
        return;
    }

    // 업데이트 탭 다운로드 — 지금 화면에 뜬 행을 CSV(엑셀 호환)로 내려받기
    if (e.target.classList.contains("changes-download-btn")) {
        const headers = ["구분", "상품명", "브랜드", "등급", "ESTNO", "어제재고", "오늘재고", "BL", "창고"];
        const rows = getChangesTabRows().map(item => [
            item.changed_fields === "__NEW__" ? "신규" : "변경",
            item.상품명, item.브랜드, item.등급, item.ESTNO,
            item._prevQty, item.재고, item.BL, item.창고,
        ]);
        downloadCsv("업데이트", headers, rows);
        return;
    }

    // 다운로드 — 예약현황/타창고매출현황 탭이 열려 있으면 그 탭의(검색/필터
    // 적용된) state.filteredReservations를 내려받고, 아니면 기존대로 재고장 표
    // (state.filteredData)를 내려받는다(2026-08-18, 두 탭 다 warehouse_main.html
    // 안으로 이관되며 페이지 구분 대신 컨테이너 표시 여부로 판단).
    if (e.target.classList.contains("main-download-btn")) {
        const reservationsOpen = document.querySelector(".reservations-container")?.style.display === "";
        const salesOpen = document.querySelector(".sales-container")?.style.display === "";

        if (reservationsOpen || salesOpen) {
            if (salesOpen) {
                const headers = ["담당자", "상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "수량", "실재고", "가용재고", "거래처", "비고", "단가", "중량", "총금액", "출고일", "상태"];
                const rows = state.filteredReservations.map(r => {
                    const unitPrice = parseUnitPrice(r.거래처);
                    const weight = parseWeight(r.거래처);
                    const total = (unitPrice !== null && weight !== null) ? unitPrice * weight : "";
                    return [
                        r.담당자 || "", r.상품명, r.브랜드, r.등급, r.ESTNO, r.BL, r.창고, r.수량,
                        r.재고, r.가용재고 ?? "", clientPrefix(r.거래처), r.비고 || "", unitPrice ?? "", weight ?? "",
                        total, r.출고일, r.status === "COMPLETED" ? "출고완료" : "",
                    ];
                });
                downloadCsv("타창고매출현황", headers, rows);
            } else {
                const headers = ["담당자", "상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "수량", "실재고", "가용재고", "거래처", "예약일", "출고일"];
                const rows = state.filteredReservations.map(r => [
                    r.담당자 || "", r.상품명, r.브랜드, r.등급, r.ESTNO, r.BL, r.창고, r.수량,
                    r.재고, r.가용재고 ?? "", r.거래처, r.홀딩일자, r.출고일,
                ]);
                downloadCsv("예약현황", headers, rows);
            }
            return;
        }

        const headers = ["상품명", "브랜드", "등급", "ESTNO", "재고", "예약", "가용", "BL", "창고", "유통기한", "평중", "비고"];
        const rows = state.filteredData.map(item => [
            item.상품명, item.브랜드, item.등급, item.ESTNO, item.재고,
            item.예약수량 || "", item.가용재고 ?? "", item.BL, item.창고,
            item.유통기한, item.평중, item.메모,
        ]);
        downloadCsv("재고", headers, rows);
        return;
    }

    // 전체 취소
    if (e.target.classList.contains("clear-btn")) {
        state.selectedItems.clear();
        state.crudData = null;
        dom.container?.classList.remove("active");
        if (dom.sideBox) dom.sideBox.innerHTML = "";
        renderTable();
        renderSelectData();
        return;
    }

    // 개별 취소 (인라인 수정행 / 홀딩 입력행 닫기)
    if (e.target.classList.contains("cancel-btn")) {
        const id = e.target.dataset.id;
        state.selectedItems.delete(id);

        if (state.selectedItems.size === 0) {
            state.crudData = null;
            dom.container?.classList.remove("active");
            if (dom.sideBox) dom.sideBox.innerHTML = "";
        }

        renderTable();
        renderSelectData();
        return;
    }

    // 개별 추가 (테이블 입력행 저장)
    if (e.target.classList.contains("select-insert-btn")) {
        const card     = e.target.closest(".insert-card");
        const name     = card?.querySelector(".insert-name")?.value || "";
        const brand    = card?.querySelector(".insert-brand")?.value || "";
        const grade    = card?.querySelector(".insert-grade")?.value || "";
        const estNo    = card?.querySelector(".insert-estNo")?.value || "";
        const qty      = card?.querySelector(".insert-qty")?.value || "";
        const bl       = card?.querySelector(".insert-bl")?.value || "";
        const warehouse = card?.querySelector(".insert-warehouse")?.value || "";
        const dueDate  = card?.querySelector(".insert-dueDate")?.value || "";
        const weight   = card?.querySelector(".insert-weight")?.value || "";
        const releaseDate = card?.querySelector(".insert-releaseDate")?.value || "";
        const holding  = card?.querySelector(".insert-holding")?.value || "";
        const dataState = card?.querySelector(".insert-state")?.value || "";
        const memo     = card?.querySelector(".input-note")?.value || "";

        const newId = await insertData(name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight, releaseDate, holding, dataState, memo);
        if (!newId) return;

        card?.remove();
        renderTable();

        showToast("✓ 추가 완료");
        state.flashIds.add(newId);
        setTimeout(() => { state.flashIds.delete(newId); renderTable(); }, 1500);
        return;
    }

    // 개별 수정
    if (e.target.classList.contains("select-update-btn")) {
        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);
        const name     = document.querySelector(`.update-name[data-id="${id}"]`)?.value;
        const brand    = document.querySelector(`.update-brand[data-id="${id}"]`)?.value;
        const grade    = document.querySelector(`.update-grade[data-id="${id}"]`)?.value;
        const estNo    = document.querySelector(`.update-estNo[data-id="${id}"]`)?.value;
        const qty      = document.querySelector(`.update-qty[data-id="${id}"]`)?.value;
        const bl       = document.querySelector(`.update-bl[data-id="${id}"]`)?.value;
        const warehouse = document.querySelector(`.update-warehouse[data-id="${id}"]`)?.value;
        const dueDate  = toDotDate(document.querySelector(`.update-dueDate[data-id="${id}"]`)?.value);
        const weight   = document.querySelector(`.update-weight[data-id="${id}"]`)?.value;
        const releaseDate = document.querySelector(`.update-releaseDate[data-id="${id}"]`)?.value;
        const holding  = document.querySelector(`.update-holding[data-id="${id}"]`)?.value;
        const dataState = document.querySelector(`.update-state[data-id="${id}"]`)?.value;
        const memo     = document.querySelector(`.update-memo[data-id="${id}"]`)?.value || "";

        // fetchAllData가 updateData 내부에서 실행되기 전에 선택 해제 → 체크박스 즉시 해제
        state.selectedItems.delete(id);

        const result = await updateData(item, null, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight, releaseDate, holding, dataState, memo);
        if (!result) { state.selectedItems.set(id, item); return; }

        state.flashIds.add(result.id);
        if (state.selectedItems.size === 0) state.crudData = null;
        renderTable();
        renderSelectData();

        showToast("✓ 수정 완료");
        setTimeout(() => { state.flashIds.delete(result.id); renderTable(); }, 1500);
        return;
    }

    // 개별 홀딩
    if (e.target.classList.contains("select-holding-btn")) {
        const id = e.target.dataset.id;
        const item = state.selectedItems.get(id);
        const qty    = document.querySelector(`.hold-qty[data-id="${id}"]`)?.value;
        const weight = document.querySelector(`.hold-weight[data-id="${id}"]`)?.value;
        const date   = document.querySelector(`.hold-releaseDate[data-id="${id}"]`)?.value;
        const note   = document.querySelector(`.hold-note[data-id="${id}"]`)?.value;
        const memo   = document.querySelector(`.hold-memo[data-id="${id}"]`)?.value || "";

        // fetchAllData가 holdingData 내부에서 실행되기 전에 선택 해제 → 체크박스 즉시 해제
        state.selectedItems.delete(id);

        const result = await holdingData(item, Number(qty), date, note, memo, weight !== "" ? weight : null);
        if (!result) { state.selectedItems.set(id, item); return; }

        // 예약은 새 행을 안 만들고 원본 행의 예약/가용 숫자만 바뀌므로, 원본 행 자체를 깜빡인다
        state.flashIds.add(id);
        if (state.selectedItems.size === 0) state.crudData = null;
        renderTable();
        renderSelectData();

        showToast("✓ 예약 완료");
        setTimeout(() => { state.flashIds.delete(id); renderTable(); }, 1500);
        return;
    }

    // 개별 삭제
    if (e.target.classList.contains("select-delete-btn")) {
        const id = e.target.dataset.id;
        const item = state.allData.find(v => v.id === id);
        if (!item) { showError("데이터를 찾을 수 없습니다."); return; }
        if (!await showConfirm("해당 항목을 삭제합니다.\n계속하시겠습니까?")) return;

        await deleteItem(item);

        state.selectedItems.delete(id);
        showToast("✓ 삭제 완료");
        renderAll();
        return;
    }

    // 전체 추가 (입력 중인 상품 행 모두 저장)
    if (e.target.classList.contains("all-insert-btn")) {
        const cards = document.querySelectorAll("tr.insert-card");
        const ids = [];
        for (const card of cards) {
            const newId = await insertData(
                card.querySelector(".insert-name")?.value || "",
                card.querySelector(".insert-brand")?.value || "",
                card.querySelector(".insert-grade")?.value || "",
                card.querySelector(".insert-estNo")?.value || "",
                card.querySelector(".insert-qty")?.value || "",
                card.querySelector(".insert-bl")?.value || "",
                card.querySelector(".insert-warehouse")?.value || "",
                card.querySelector(".insert-dueDate")?.value || "",
                card.querySelector(".insert-weight")?.value || "",
                card.querySelector(".insert-releaseDate")?.value || "",
                card.querySelector(".insert-holding")?.value || "",
                card.querySelector(".insert-state")?.value || "",
                card.querySelector(".insert-memo")?.value || "",
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-insert)로 처리
            );
            if (newId) ids.push(newId);
        }
        if (ids.length === 0) return;
        pushUndo({ type: "bulk-insert", ids });
        if (dom.insertRowsBody) dom.insertRowsBody.innerHTML = "";
        showToast(`✓ ${ids.length}건 추가 완료`);
        await fetchAllData();
        ids.forEach(id => state.flashIds.add(id));
        renderTable();
        setTimeout(() => { ids.forEach(id => state.flashIds.delete(id)); renderTable(); }, 1500);
        return;
    }

    // 전체 수정
    if (e.target.classList.contains("all-update-btn")) {
        const rows = document.querySelectorAll("tr.update-row-edit[data-id]");
        const backups = [];
        for (const row of rows) {
            const id = row.dataset.id;
            const item = state.allData.find(v => v.id === id);
            const result = await updateData(
                item, id,
                row.querySelector(".update-name")?.value,
                row.querySelector(".update-brand")?.value,
                row.querySelector(".update-grade")?.value,
                row.querySelector(".update-estNo")?.value,
                row.querySelector(".update-qty")?.value,
                row.querySelector(".update-bl")?.value,
                row.querySelector(".update-warehouse")?.value,
                toDotDate(row.querySelector(".update-dueDate")?.value),
                row.querySelector(".update-weight")?.value,
                row.querySelector(".update-releaseDate")?.value,
                row.querySelector(".update-holding")?.value,
                row.querySelector(".update-state")?.value,
                row.querySelector(".update-memo")?.value || "",
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-update)로 처리
            );
            if (result) backups.push(result);
        }
        if (backups.length > 0) {
            pushUndo({ type: "bulk-update", backups: backups.map(b => ({ id: b.rawId, prevData: b.prevData, azy: b.azy })) });
        }
        state.selectedItems.clear();
        state.crudData = null;
        showToast("✓ 수정 완료");
        await fetchAllData();
        return;
    }

    // 전체 홀딩
    if (e.target.classList.contains("all-holding-btn")) {
        const rows = document.querySelectorAll("tr.holding-insert-row[data-id]");
        const backups = [];
        for (const row of rows) {
            const id = row.dataset.id;
            const item = state.selectedItems.get(id);
            const holdWeight = row.querySelector(".hold-weight")?.value;
            const result = await holdingData(
                item,
                Number(row.querySelector(".hold-qty")?.value),
                row.querySelector(".hold-releaseDate")?.value,
                row.querySelector(".hold-note")?.value,
                row.querySelector(".hold-memo")?.value || "",
                holdWeight !== "" ? holdWeight : null,
                true  // noUndo — 전체 undo는 아래 pushUndo(bulk-holding)로 처리
            );
            if (result) backups.push(result);
        }
        if (backups.length > 0) {
            pushUndo({ type: "bulk-reservation", ids: backups.map(b => b.reservationId) });
        }
        state.selectedItems.clear();
        state.crudData = null;
        showToast("✓ 예약 완료");
        await fetchAllData();
        return;
    }

    // 전체 삭제
    if (e.target.classList.contains("all-delete-btn")) {
        const count = state.selectedItems.size;
        if (!await showConfirm(`선택한 ${count}건을 삭제합니다.\n계속하시겠습니까?`)) return;
        try {
            const backups = [];
            for (const [, item] of state.selectedItems) {
                backups.push({ ...item });
                await deleteItem(item, true, true);  // noUndo=true, noFetch=true (마지막에 한 번만)
            }
            pushUndo({ type: "bulk-delete", items: backups.map(b => ({
                azy: b.raw?._source === "azy",
                data: {
                    상품명: b.name || "",
                    브랜드: b.brand || "",
                    등급: b.grade || "",
                    ESTNO: b.estNo || "",
                    재고: b.qty || 0,
                    BL: b.bl || "",
                    창고: b.warehouse || "",
                    유통기한: b.dueDate || "",
                    평중: b.weight || 0,
                    출고일: b.releaseDate || "",
                    홀딩: b.holding || "",
                    상태: b.dataState || "",
                    메모: b.memo || "",
                },
            })) });
            state.selectedItems.clear();
            await fetchAllData();
            showToast("✓ 삭제 완료");
            renderAll();
        } catch (err) {
            console.error("전체 삭제 실패:", err);
            showError("삭제 중 오류가 발생했습니다: " + err.message);
        }
        return;
    }

    // 되돌리기 — 예약/출고 현황 탭 관련 작업(2026-08-18)도 되돌릴 수 있게 되면서,
    // 메인 테이블뿐 아니라 예약/출고 탭도 같이 새로고침해야 결과가 바로 보인다.
    if (e.target.classList.contains("rollback-btn")) {
        await undoLastAction();
        state.selectedItems.clear();
        state.crudData = null;
        await fetchAllData();
        await refreshReservationViews();
        return;
    }

}
