import { state } from "./state.js";
import { renderTable, updateSortHeaders, renderBulkActionBar, renderChangesTab, getChangesTabRows, renderReservationsTab, renderSalesTab, renderPriceTab, renderOrderSheetTab, priceInsertRowHtml, PRICE_FIELDS, priceFieldClass, clientPrefix, parseUnitPrice, parseWeight, buildClientWithDetails, outboundInsertRowHtml, createUpdateCard, createHoldingCard } from "./table.js";
import { renderSelectData, renderInsert, createInsertRow } from "./panel.js";
import { addSelectedItem } from "./data_eda.js";
import { holdingData, insertData, updateData, deleteItem } from "./crud.js";
import { getReservationsByPk, cancelReservation, useReservation, updateReservation, updateOutbound, cancelOutbound, createOutbound, registerOutboundFromReservation, toggleOutboundComplete, toggleOutboundRegister, toggleOutboundStockRelease, createPrice, updatePrice, deletePrice } from "./firestoreService.js";
import { dom } from "./dom.js";
import { calculateTotal } from "./input_calculater.js";
import { undoLastAction, pushUndo } from "./crud_history.js";
import { fetchAllData } from "./firebase.js";
import { showToast, showError, showConfirm, showEditReservationModal, showRegisterOutboundModal, showNoteModal, showCancelOutboundModal, showAlertModal, showPriceExportModal, showEditPriceModal, showReservationDetailModal, showBulkEditModal } from "./ui.js";
import { getStoredUser, applyRoleVisibility, hasPriceEditAccess } from "./login.js";
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

// 타창고매출현황 비고 저장 시 내림 상태 동기화(2026-08-25) — 비고에 값이 있으면
// 내림 ON, 비우면 OFF. toggleOutboundStockRelease는 순수 토글이라 원하는 상태와
// 현재 상태가 다를 때만 호출(같으면 그대로 둠, 불필요한 토글로 되돌아가는 것 방지).
async function syncStockReleaseWithRemark(id, remarkValue) {
    const row = state.filteredReservations?.find(r => r.id === id);
    const wantDropped = !!String(remarkValue ?? "").trim();
    const currentDropped = !!row?.수량내림;
    if (wantDropped === currentDropped) return;
    try {
        await toggleOutboundStockRelease(id);
    } catch (err) {
        showError(err.message || "내림 상태 동기화에 실패했습니다.");
    }
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
const TAB_CONTAINERS = [".changes-container", ".reservations-container", ".sales-container", ".price-container", ".order-sheet-container"];
const TAB_BUTTONS = [".changes-tab-btn", ".reservations-tab-btn", ".sales-tab-btn", ".price-tab-btn", ".order-sheet-tab-btn"];

// 탭 전환 시 재고장 검색/필터 초기화(2026-08-19) — 재고장에서 검색하다 예약현황/
// 타창고매출현황으로 넘어가도 그 값이 그대로 남아 다른 탭 목록까지 걸러버리던
// 문제. 검색1·검색2 입력창과 4개 드롭다운을 전부 비운다.
function clearSearchAndFilters() {
    if (dom.searchInput) dom.searchInput.value = "";
    if (dom.searchInput2) dom.searchInput2.value = "";
    [".show-warehouse", ".show-product-name", ".show-brand", ".show-state"].forEach(sel => {
        const el = document.querySelector(sel);
        if (el) el.value = "";
    });
}

// 팝업 모달(수정/예약) 일괄 처리 결과 안내(2026-08-25 버그 수정) — 이전엔 실패한
// 행이 있어도(예: 가용재고 부족) holdingData/updateData가 개별로 띄운 에러 토스트를
// 루프 끝의 무조건 "완료" 토스트가 그대로 덮어써서 실제로는 실패했는데 성공한 것처럼
// 보였다. 성공/실패 건수를 세서 실패가 하나라도 있으면 성공 토스트를 띄우지 않는다.
function reportBulkResult(label, successCount, failCount) {
    if (failCount === 0) {
        showToast(`✓ ${label} 완료 (${successCount}건)`);
    } else if (successCount > 0) {
        showError(`${label} ${successCount}건 완료, ${failCount}건 실패`);
    } else {
        showError(`${label} 실패 (${failCount}건)`);
    }
}

function switchTab(btnClass, containerSelector, render) {
    const tableContainer = document.querySelector(".table-container");
    const targetContainer = document.querySelector(containerSelector);
    if (!tableContainer || !targetContainer) return;
    const opening = targetContainer.style.display === "none";

    TAB_CONTAINERS.forEach(sel => { const el = document.querySelector(sel); if (el) el.style.display = "none"; });
    TAB_BUTTONS.forEach(sel => document.querySelector(sel)?.classList.remove("active"));
    tableContainer.style.display = opening ? "none" : "";

    // 컨테이너 표시부터 먼저 뒤집어야 applyRoleVisibility의 _currentTabName()이
    // 새 탭을 제대로 감지한다(2026-08-19 버그: 이 순서가 뒤바뀌어 있어서 탭 전환
    // 직후엔 항상 "main"으로 오판되던 문제 — 전략단가 탭 검색/필터가 안 숨던 원인).
    if (opening) {
        targetContainer.style.display = "";
        document.querySelector(`.${btnClass}`)?.classList.add("active");
    }

    clearSearchAndFilters();
    renderTable();
    applyRoleVisibility(getStoredUser()?.권한);

    if (opening) {
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

// 모바일 다운로드 — 엑셀(CSV)은 스프레드시트 앱 없이는 열어보기 불편해서 이미지로
// 대신 내려받는다(2026-08-20). 카드를 그대로 캡처하면 항목 수만큼 세로로 한없이
// 길어져서(재고장 전체면 4~5만px) 대신 CSV랑 똑같은 표 형태(헤더+행)를 화면 밖에
// 그려서 그걸 캡처 — 데이터 형식은 엑셀과 동일하게, 파일 형식만 이미지로.
function dataTableHtml(headers, rows) {
    const esc = v => String(v ?? "");
    // color 명시 필수 — 페이지 전역 CSS의 "thead { color: #fff }"(재고장 표 헤더용)가
    // 상속돼서 배경(#f1f5f9)과 겹쳐 글자가 안 보였음(2026-08-20 버그 리포트).
    const th = headers.map(h => `<th style="border:1px solid #cbd5e1;padding:5px 10px;background:#f1f5f9;color:#1e293b;white-space:nowrap;">${esc(h)}</th>`).join("");
    const trs = rows.map(r => `<tr>${r.map(c => `<td style="border:1px solid #cbd5e1;padding:5px 10px;white-space:nowrap;">${esc(c)}</td>`).join("")}</tr>`).join("");
    // width:max-content — 안 그러면 nowrap 셀 합이 화면 폭보다 넓을 때 table이
    // 뷰포트 폭으로 눌려 잘린 채로 캡처된다(2026-08-20 실측: offsetWidth가
    // scrollWidth보다 작게 나옴). max-content로 내용에 맞는 실제 폭을 갖게 함.
    return `<table style="border-collapse:collapse;font-family:sans-serif;font-size:13px;background:#fff;color:#1e293b;width:max-content;"><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table>`;
}

async function downloadTableAsImage(filenamePrefix, headers, rows) {
    if (typeof html2canvas !== "function") {
        showError("이미지 다운로드를 사용할 수 없습니다.");
        return;
    }
    // 행이 많으면(특히 필터 안 건 재고장 전체) 캡처에 몇 초 걸려서 아무 반응
    // 없어 보일 수 있어 안내(2026-08-20).
    showToast("이미지 생성 중...", "info");
    const wrap = document.createElement("div");
    // 화면 밖(예: left:-99999px)에 두면 html2canvas가 캡처 영역 크기를 잘못
    // 계산해 세로 몇백px짜리가 가로 10만px로 찍히는 버그가 있어서(2026-08-20
    // 실측), 대신 맨 위에 실제로 잠깐 덮어씌워서 캡처 — 클릭이라는 명시적
    // 동작 직후라 아주 잠깐 화면이 하얗게 덮이는 건 자연스럽다.
    wrap.style.cssText = "position:fixed; inset:0; z-index:99999; background:#fff; overflow:auto;";
    wrap.innerHTML = dataTableHtml(headers, rows);
    document.body.appendChild(wrap);
    try {
        const canvas = await html2canvas(wrap.firstElementChild, { backgroundColor: "#ffffff", scale: 2 });
        const today = new Date();
        const pad = n => String(n).padStart(2, "0");
        const filename = `${filenamePrefix}_${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}.png`;
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
        const file = new File([blob], filename, { type: "image/png" });

        // 아이폰 사파리는 <a download>가 사진첩 저장으로 안 이어지고 그냥 새 탭에서
        // 열리기만 해서(2026-08-20 버그 리포트) 파일 공유가 되면 네이티브 공유
        // 시트(사진에 저장 포함)를 띄우고, 안 되는 환경(대부분 데스크톱)에서만
        // 기존 다운로드 링크로 폴백한다.
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            try {
                await navigator.share({ files: [file], title: filenamePrefix });
                showToast("✓ 이미지 공유됨");
                return;
            } catch (err) {
                if (err.name === "AbortError") return; // 사용자가 공유 시트에서 취소
                // 그 외 실패면 아래 다운로드 링크로 폴백
            }
        }

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast("✓ 이미지 다운로드 완료");
    } finally {
        wrap.remove();
    }
}

// CSV/이미지 중 화면 폭에 맞게 골라 내려받기 — downloadCsv를 부르던 자리를 전부 이걸로 교체.
async function exportTable(filenamePrefix, headers, rows) {
    if (window.innerWidth <= 768) await downloadTableAsImage(filenamePrefix, headers, rows);
    else downloadCsv(filenamePrefix, headers, rows);
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

    // 다운로드 버튼 라벨 — 모바일(<=768px)에서는 실제로 이미지를 받으니(아래
    // main-download-btn 핸들러와 같은 기준) 라벨도 "이미지 다운로드"로(2026-08-20).
    const updateDownloadBtnLabel = () => {
        const btn = document.querySelector(".main-download-btn");
        if (btn) btn.textContent = window.innerWidth <= 768 ? "이미지 다운로드" : "엑셀 다운로드";
    };
    updateDownloadBtnLabel();
    window.addEventListener("resize", updateDownloadBtnLabel);

    if (toggleDesktopViewBtn && viewportMeta) {
        const applyForceDesktop = (forced) => {
            document.body.classList.toggle("force-desktop-view", forced);
            viewportMeta.setAttribute("content", forced ? DESKTOP_VIEWPORT : MOBILE_VIEWPORT);
            toggleDesktopViewBtn.textContent = forced ? "모바일" : "PC";
            toggleDesktopViewBtn.title = forced ? "모바일 화면으로 보기" : "PC 화면으로 보기";
            updateDownloadBtnLabel();
        };
        applyForceDesktop(localStorage.getItem(FORCE_DESKTOP_KEY) === "1");
        toggleDesktopViewBtn.addEventListener("click", () => {
            const forced = !document.body.classList.contains("force-desktop-view");
            applyForceDesktop(forced);
            localStorage.setItem(FORCE_DESKTOP_KEY, forced ? "1" : "0");
        });
    }

    // 마우스오버 예약/출고 미리보기 카드는 제거(2026-08-20) — 예약 열 배지를
    // 눌러서 보는 팝업(showReservationDetailModal)으로 대체.
    const tableEl = document.querySelector(".table-wrap table");
    if (tableEl) {
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
            // 체크한 사람 이름을 같이 보내서 서버가 수정자 컬럼에 기록(2026-08-25) —
            // 행 색을 "지금 보는 사람"이 아니라 "실제로 체크한 사람" 기준으로
            // 모두에게 동일하게 보여주기 위함.
            toggleOutboundRegister(id, getStoredUser()?.이름 || "")
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
        if (e.target.id === "price-category-filter") {
            state.priceCategoryFilter = e.target.value;
            renderPriceTab();
        }
        if (e.target.id === "price-brand-filter") {
            state.priceBrandFilter = e.target.value;
            renderPriceTab();
        }
        if (e.target.id === "reservations-warehouse-filter") {
            state.reservationsWarehouseFilter = e.target.value;
            renderReservationsTab();
        }
        if (e.target.id === "reservations-brand-filter") {
            state.reservationsBrandFilter = e.target.value;
            renderReservationsTab();
        }
        if (e.target.id === "sales-warehouse-filter") {
            state.salesWarehouseFilter = e.target.value;
            renderSalesTab();
        }
        if (e.target.id === "sales-brand-filter") {
            state.salesBrandFilter = e.target.value;
            renderSalesTab();
        }
        if (e.target.id === "sales-manager-filter") {
            state.salesManagerFilter = e.target.value;
            renderSalesTab();
        }
        if (e.target.id === "changes-warehouse-filter") {
            state.changesWarehouseFilter = e.target.value;
            renderChangesTab();
        }
        if (e.target.id === "changes-brand-filter") {
            state.changesBrandFilter = e.target.value;
            renderChangesTab();
        }
    });

    let priceSearchTimer = null;
    let reservationsSearchTimer = null;
    let salesSearchTimer = null;
    let changesSearchTimer = null;
    document.addEventListener("input", (e) => {
        if (e.target.id === "price-search") {
            clearTimeout(priceSearchTimer);
            priceSearchTimer = setTimeout(() => {
                state.priceSearch = e.target.value;
                renderPriceTab();
            }, 200);
        }
        if (e.target.id === "reservations-search") {
            clearTimeout(reservationsSearchTimer);
            reservationsSearchTimer = setTimeout(() => {
                state.reservationsSearch = e.target.value;
                renderReservationsTab();
            }, 200);
        }
        if (e.target.id === "sales-search") {
            clearTimeout(salesSearchTimer);
            salesSearchTimer = setTimeout(() => {
                state.salesSearch = e.target.value;
                renderSalesTab();
            }, 200);
        }
        if (e.target.id === "changes-search") {
            clearTimeout(changesSearchTimer);
            changesSearchTimer = setTimeout(() => {
                state.changesSearch = e.target.value;
                renderChangesTab();
            }, 200);
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
                        await syncStockReleaseWithRemark(id, newValue);
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

        // 타창고매출현황 — 수량 칸 더블클릭 인라인 수정(2026-08-24, 비고 칸과 동일 패턴).
        const qtyCell = e.target.closest(".sales-qty-cell");
        if (qtyCell) {
            if (qtyCell.querySelector("input")) return;
            const id = qtyCell.dataset.id;
            const original = Number(qtyCell.dataset.value || 0);
            qtyCell.innerHTML = `<input type="number" min="1" class="sales-qty-input" value="${original}">`;
            const input = qtyCell.querySelector("input");
            input.focus();
            input.select();

            let done = false;
            const finish = async (save) => {
                if (done) return;
                done = true;
                const newValue = Number(input.value);
                if (save && Number.isInteger(newValue) && newValue > 0 && newValue !== original) {
                    try {
                        await updateOutbound(id, { 수량: newValue });
                        _logActivity("outbound", id, "수정", { 수량: original }, { 수량: newValue }, "수량 변경");
                        showToast("✓ 수량 저장됨");
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

        // 타창고매출현황 — 거래처/단가/중량 칸 더블클릭 인라인 수정(2026-08-24).
        // 세 칸 다 outbound.거래처 문자열 하나("이름 가격원 중량kg")에 같이
        // 인코딩돼 있어서(table.js clientPrefix/parseUnitPrice/parseWeight 참고),
        // 어느 칸을 고치든 나머지 두 값은 원본에서 그대로 떼와 다시 조합해서 저장.
        const clientCell = e.target.closest(".sales-client-cell");
        const priceCell = e.target.closest(".sales-price-cell");
        const weightCell = e.target.closest(".sales-weight-cell");
        const clientLikeCell = clientCell || priceCell || weightCell;
        if (clientLikeCell) {
            if (clientLikeCell.querySelector("input")) return;
            const id = clientLikeCell.dataset.id;
            const rawClient = clientLikeCell.dataset.raw || "";
            const prefix = clientPrefix(rawClient);
            const price = parseUnitPrice(rawClient);
            const weight = parseWeight(rawClient);
            const field = clientCell ? "prefix" : priceCell ? "price" : "weight";
            const current = field === "prefix" ? prefix : field === "price" ? (price ?? "") : (weight ?? "");
            const isNumberField = field !== "prefix";
            clientLikeCell.innerHTML = `<input type="${isNumberField ? "number" : "text"}" ${isNumberField ? 'step="0.01" min="0"' : ""} class="sales-inline-input" value="${String(current).replace(/"/g, "&quot;")}">`;
            const input = clientLikeCell.querySelector("input");
            input.focus();
            input.select();

            let done = false;
            const finish = async (save) => {
                if (done) return;
                done = true;
                if (save) {
                    const raw = input.value.trim();
                    let newPrefix = prefix, newPrice = price, newWeight = weight;
                    if (field === "prefix") newPrefix = raw;
                    else if (field === "price") newPrice = raw === "" ? null : Number(raw);
                    else newWeight = raw === "" ? null : Number(raw);
                    const newClient = buildClientWithDetails(newPrefix, newPrice, newWeight);
                    if (newClient !== rawClient) {
                        try {
                            await updateOutbound(id, { 거래처: newClient });
                            _logActivity("outbound", id, "수정", { 거래처: rawClient }, { 거래처: newClient }, "거래처/단가/중량 변경");
                            showToast("✓ 저장됨");
                        } catch (err) {
                            showError(err.message || "저장에 실패했습니다.");
                        }
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

        // 전략단가 — 행 더블클릭하면 그 행 전체가 입력창으로 바뀜(2026-08-19).
        // 여러 칸을 한꺼번에 고치는 거라 비고 칸처럼 blur 하나로는 안 되고,
        // 포커스가 행 밖으로 완전히 나갔을 때만 저장한다(칸 사이 Tab 이동은 무시).
        const priceRow = e.target.closest("tr.price-row");
        if (priceRow) {
            if (!hasPriceEditAccess(getStoredUser()?.권한)) return;
            if (priceRow.querySelector("input")) return;
            const id = priceRow.dataset.id;
            const original = state.filteredPrices.find(r => String(r.id) === id);
            if (!original) return;
            const cells = priceRow.querySelectorAll("td");
            PRICE_FIELDS.forEach((f, i) => {
                const td = cells[i];
                const input = document.createElement("input");
                input.className = "price-edit-input";
                input.type = f.type;
                if (f.type === "number") input.step = "any";
                input.value = original[f.key] ?? "";
                td.innerHTML = "";
                td.appendChild(input);
            });
            const firstInput = priceRow.querySelector("input");
            firstInput?.focus();
            firstInput?.select();

            let done = false;

            // 수정 모드에서만 삭제 버튼 노출(2026-08-19) — 평소엔 액션 칸이 비어있음
            const actionsCell = cells[PRICE_FIELDS.length];
            if (actionsCell) {
                actionsCell.innerHTML = `<button type="button" class="price-delete-btn">삭제</button>`;
                actionsCell.querySelector(".price-delete-btn").addEventListener("click", async () => {
                    if (done) return;
                    done = true;
                    if (!await showConfirm(`"${original.품목 || "이 항목"}"을(를) 삭제합니다.\n계속하시겠습니까?`)) {
                        done = false;
                        return;
                    }
                    try {
                        await deletePrice(id);
                        _logActivity("price", id, "삭제", original, null, "전략단가 삭제");
                        showToast("✓ 삭제됨");
                    } catch (err) {
                        showError(err.message || "삭제에 실패했습니다.");
                    }
                    renderPriceTab();
                });
            }
            const finish = async (save) => {
                if (done) return;
                done = true;
                if (save) {
                    const fields = {};
                    PRICE_FIELDS.forEach((f, i) => {
                        const raw = cells[i].querySelector("input")?.value ?? "";
                        fields[f.key] = f.type === "number" ? (raw === "" ? null : Number(raw)) : (raw || null);
                    });
                    const changed = Object.keys(fields).some(k => String(fields[k] ?? "") !== String(original[k] ?? ""));
                    if (changed) {
                        try {
                            await updatePrice(id, fields);
                            _logActivity("price", id, "수정", original, fields, "전략단가 수정");
                            showToast("✓ 저장됨");
                        } catch (err) {
                            showError(err.message || "저장에 실패했습니다.");
                        }
                    }
                }
                renderPriceTab();
            };
            priceRow.querySelectorAll("input").forEach(input => {
                input.addEventListener("keydown", (ke) => {
                    if (ke.key === "Enter") { ke.preventDefault(); finish(true); }
                    if (ke.key === "Escape") { ke.preventDefault(); finish(false); }
                });
                input.addEventListener("blur", () => {
                    setTimeout(() => { if (!priceRow.contains(document.activeElement)) finish(true); }, 0);
                });
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
        renderSelectData(); // "총 N행, M박스 선택" 배지도 같이 지워야 함(안 그러면 마지막 선택 해제해도 남아있음)
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
    // 예약현황/타창고매출현황 열 클릭 정렬(2026-08-25) — 재고장 표의 th[data-key]
    // 클릭 정렬(오름차→내림차→해제 순환)과 같은 로직이지만, 이 두 탭은 필터가
    // 바뀔 때마다 표 전체가 innerHTML로 새로 그려져서 th에 리스너를 한 번만 붙여둘
    // 수 없다 — document 위임 클릭으로 매번 새로 그려진 th도 잡히게 한다.
    const sortTh = e.target.closest(".reservations-table thead th[data-key]");
    if (sortTh) {
        const key = sortTh.dataset.key;
        const isSalesTh = !!sortTh.closest(".sales-container");
        const cols = isSalesTh ? state.salesSortColumns : state.reservationsSortColumns;
        const idx = cols.findIndex(s => s.key === key);
        if (idx === -1) cols.push({ key, dir: 1 });
        else if (cols[idx].dir === 1) cols[idx].dir = 2;
        else cols.splice(idx, 1);
        if (isSalesTh) renderSalesTab(); else renderReservationsTab();
        return;
    }

    // 예약 수량 클릭 — 팝업으로 거래처별 예약/출고 목록 표시(조회 전용, 취소
    // 버튼 없음 — 여러 군데서 가능하면 혼란스러워질 수 있어 2026-08-06 결정,
    // 2026-08-20 아코디언에서 모달로 변경).
    if (e.target.classList.contains("view-reservations-btn")) {
        const pk = e.target.dataset.pk;
        const reservations = await getReservationsByPk(pk);
        await showReservationDetailModal(reservations);
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

    // 추가 버튼 — 전략단가 탭에서는 표 맨 위에 입력행을 띄운다(2026-08-19).
    if (e.target.classList.contains("insert-btn") && document.querySelector(".price-container")?.style.display === "") {
        const body = document.getElementById("price-insert-rows");
        if (!body) return;
        body.innerHTML = body.children.length > 0 ? "" : priceInsertRowHtml();
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

    // 전략단가 입력행 — 저장
    if (e.target.classList.contains("save-price-insert-btn")) {
        const row = e.target.closest("tr");
        const fields = {};
        PRICE_FIELDS.forEach(f => {
            const el = row.querySelector(`.${priceFieldClass(f.key)}`);
            const raw = el?.value ?? "";
            fields[f.key] = f.type === "number" ? (raw === "" ? null : Number(raw)) : (raw || null);
        });
        if (!fields.품목) { showError("품목은 필수입니다."); return; }
        try {
            const res = await createPrice(fields);
            showToast("✓ 추가됨");
            if (res?.id) _logActivity("price", res.id, "삽입", null, fields, `${fields.품목} 전략단가 추가`);
            renderPriceTab();
        } catch (err) {
            showError(err.message || "추가에 실패했습니다.");
        }
        return;
    }

    // 전략단가 입력행 — 취소
    if (e.target.classList.contains("cancel-price-insert-btn")) {
        document.getElementById("price-insert-rows").innerHTML = "";
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

    // 수정 버튼 — 선택한 행을 팝업 모달로 편집(2026-08-24 전체 공개, 여러 행 선택해도
    // 모달 하나에 전부 들어감). 기존 표 안 인라인 편집 방식은 대체됨.
    if (e.target.classList.contains("update-btn")) {
        if (state.selectedItems.size === 0) { showError("수정할 상품을 선택하세요."); return; }
        // createUpdateRow/updateData 둘 다 state.allData의 원본(한글 키) 형태를
        // 기대함 — state.selectedItems는 정규화된(영문 키) 형태라 여기 쓰면 안 됨
        // (addSelectedItem이 normalizeItem을 거쳐서 저장하기 때문).
        const ids = [...state.selectedItems.keys()];
        const items = ids.map(id => state.allData.find(v => v.id === id)).filter(Boolean);
        const rowsHtml = items.map(createUpdateCard).join("");
        showBulkEditModal(`선택 상품 수정 (${items.length}건)`, rowsHtml, {
                onSave: async (overlay) => {
                    const rows = overlay.querySelectorAll(".bulk-edit-card[data-id]");
                    const backups = [];
                    let failCount = 0;
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
                            true
                        );
                        if (result) backups.push(result); else failCount++;
                    }
                    if (backups.length > 0) {
                        pushUndo({ type: "bulk-update", backups: backups.map(b => ({ id: b.rawId, prevData: b.prevData, azy: b.azy })) });
                    }
                    state.selectedItems.clear();
                    state.crudData = null;
                    reportBulkResult("수정", backups.length, failCount);
                    await fetchAllData();
                },
            });
            return;
    }

    // 홀딩 버튼 — 선택한 행을 팝업 모달로 예약(2026-08-24 전체 공개). 위 update-btn과
    // 동일한 원리.
    if (e.target.classList.contains("holding-btn")) {
        if (state.selectedItems.size === 0) { showError("예약할 상품을 선택하세요."); return; }
        // createHoldingInsertRow는 원본(한글 키, state.allData) 형태를 기대하지만
        // holdingData는 정규화된(영문 키, state.selectedItems — addSelectedItem이
        // normalizeItem을 거쳐서 저장) 형태를 기대함 — 화면 생성과 저장에 서로
        // 다른 소스를 써야 함(기존 개별/전체 홀딩 처리 로직과 동일한 이유).
        const ids = [...state.selectedItems.keys()];
        const items = ids.map(id => state.allData.find(v => v.id === id)).filter(Boolean);
        const rowsHtml = items.map(createHoldingCard).join("");
        showBulkEditModal(`선택 상품 예약 (${items.length}건)`, rowsHtml, {
                onSave: async (overlay) => {
                    const rows = overlay.querySelectorAll(".bulk-edit-card[data-id]");
                    const backups = [];
                    let failCount = 0;
                    for (const row of rows) {
                        const id = row.dataset.id;
                        const item = state.selectedItems.get(id);
                        const holdWeight = row.querySelector(".hold-weight")?.value;
                        // 거래처/단가를 입력 시점에 따로 받아서(2026-08-24) "거래처명 단가원"
                        // 형태로 합쳐 저장 — 예약현황/타창고매출현황 둘 다 이 문자열을
                        // clientPrefix/parseUnitPrice로 다시 갈라 거래처·단가 열에 보여준다.
                        const client = row.querySelector(".hold-client")?.value || "";
                        const price = row.querySelector(".hold-price")?.value;
                        const combinedClient = buildClientWithDetails(client, price !== "" ? price : null, null);
                        // 담당자 안 고르면 "소매" 처리(2026-08-24) — 미지정으로 남기지 않고
                        // 담당자 없는 소매 판매라는 뜻으로 명시적인 값을 넣는다.
                        const note = row.querySelector(".hold-note")?.value?.trim() || "소매";
                        const result = await holdingData(
                            item,
                            Number(row.querySelector(".hold-qty")?.value),
                            row.querySelector(".hold-releaseDate")?.value,
                            note,
                            combinedClient,
                            holdWeight !== "" ? holdWeight : null,
                            true
                        );
                        if (result) backups.push(result); else failCount++;
                    }
                    if (backups.length > 0) {
                        pushUndo({ type: "bulk-reservation", ids: backups.map(b => b.reservationId) });
                    }
                    state.selectedItems.clear();
                    state.crudData = null;
                    reportBulkResult("예약", backups.length, failCount);
                    await fetchAllData();
                },
            });
            return;
    }

    // 업데이트/예약현황/타창고매출현황/전략단가 탭 — 재고장 표와 서로 배타적으로
    // 토글(2026-08-18, sales.html·price.html을 별도 페이지 대신 탭으로 통합하면서
    // 탭 개수가 2→4로 늘어 페어별 토글 대신 공용 switchTab으로 정리).
    if (e.target.classList.contains("changes-tab-btn")) { switchTab("changes-tab-btn", ".changes-container", renderChangesTab); return; }
    if (e.target.classList.contains("reservations-tab-btn")) { switchTab("reservations-tab-btn", ".reservations-container", renderReservationsTab); return; }
    if (e.target.classList.contains("sales-tab-btn")) { switchTab("sales-tab-btn", ".sales-container", renderSalesTab); return; }
    if (e.target.classList.contains("price-tab-btn")) { switchTab("price-tab-btn", ".price-container", renderPriceTab); return; }
    if (e.target.classList.contains("order-sheet-tab-btn")) { switchTab("order-sheet-tab-btn", ".order-sheet-container", renderOrderSheetTab); return; }

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
        const canRemark = e.target.dataset.canRemark === "1";
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
        const result = await showEditReservationModal(current, { showPrice, canRemark });
        if (!result) return;
        if (!Number.isInteger(result.수량) || result.수량 <= 0) { showError("올바른 수량을 입력하세요."); return; }

        const newClient = showPrice ? buildClientWithDetails(result.거래처명, result.단가, result.중량) : result.거래처;

        const fields = {};
        const prev = {};
        if (result.수량 !== current.수량) { fields.수량 = result.수량; prev.수량 = current.수량; }
        if (result.출고일 !== current.출고일) { fields.출고일 = result.출고일; prev.출고일 = current.출고일; }
        if (newClient !== rawClient) { fields.거래처 = newClient; prev.거래처 = rawClient; }
        if (showPrice && canRemark && result.비고 !== current.비고) { fields.비고 = result.비고; prev.비고 = current.비고; }
        if (Object.keys(fields).length === 0) return;

        // showPrice(=sales.html)면 outbound 항목 — 출고일을 오늘이 아닌 날짜로
        // 바꾸면 서버가 자동으로 예약 테이블로 다시 옮긴다(update_outbound 안에서 처리).
        try {
            if (showPrice) await updateOutbound(id, fields); else await updateReservation(id, fields);
            pushUndo({ type: showPrice ? "outbound-fields" : "reservation-fields", id, prev });
            _logActivity(showPrice ? "outbound" : "reservation", id, "수정", prev, fields, `${Object.keys(fields).join(", ")} 변경`);
            if (showPrice && "비고" in fields) await syncStockReleaseWithRemark(id, fields.비고);
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

    // 전략단가 모바일 카드 — 수정/삭제(2026-08-19). 데스크톱은 더블클릭으로 행을
    // 통째로 입력창으로 바꾸지만 카드는 탭이 더블클릭 인식이 안 좋아 모달로 대신.
    if (e.target.classList.contains("price-card-edit-btn")) {
        if (!hasPriceEditAccess(getStoredUser()?.권한)) return;
        const id = e.target.dataset.id;
        const original = state.filteredPrices.find(r => String(r.id) === id);
        if (!original) return;
        const result = await showEditPriceModal(original);
        if (!result) return;
        const changed = Object.keys(result).some(k => String(result[k] ?? "") !== String(original[k] ?? ""));
        if (!changed) return;
        try {
            await updatePrice(id, result);
            _logActivity("price", id, "수정", original, result, "전략단가 수정");
            showToast("✓ 저장됨");
        } catch (err) {
            showError(err.message || "저장에 실패했습니다.");
        }
        renderPriceTab();
        return;
    }
    if (e.target.classList.contains("price-card-delete-btn")) {
        if (!hasPriceEditAccess(getStoredUser()?.권한)) return;
        const id = e.target.dataset.id;
        const original = state.filteredPrices.find(r => String(r.id) === id);
        if (!await showConfirm(`"${original?.품목 || "이 항목"}"을(를) 삭제합니다.\n계속하시겠습니까?`)) return;
        try {
            await deletePrice(id);
            _logActivity("price", id, "삭제", original, null, "전략단가 삭제");
            showToast("✓ 삭제됨");
        } catch (err) {
            showError(err.message || "삭제에 실패했습니다.");
        }
        renderPriceTab();
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

    // 예약 현황 탭 — 출고등록(2026-08-24 재설계: outbound로 안 옮기고 예약
    // 수량 중 일부/전체의 출고일자만 지정 — 실제 이동은 출고일이 오늘이 됐을 때
    // migrate_due_reservations_to_outbound가 자동으로 처리).
    if (e.target.classList.contains("register-outbound-btn")) {
        const id = e.target.dataset.id;
        const maxQty = Number(e.target.dataset.qty || 0);
        const result = await showRegisterOutboundModal({ 수량: maxQty });
        if (!result) return;
        const prev = state.filteredReservations.find(row => row.id === id);
        try {
            const res = await registerOutboundFromReservation(id, result);
            if (res?.id === id) {
                // 전체 등록 — 그 행의 출고일(+거래처)만 바뀜, 그대로 되돌리기 가능.
                pushUndo({ type: "reservation-fields", id, prev: { 출고일: prev?.출고일 ?? "", 거래처: prev?.거래처 ?? "" } });
            } else if (res?.id) {
                // 부분 등록 — 새 예약 행이 갈라져 나옴, 되돌리려면 그 행을 취소하고
                // 원래 행 수량을 복구해야 함.
                pushUndo({ type: "outbound-register-split", newId: res.id, originalId: id, splitQty: result.수량, prevQty: maxQty });
            }
            _logActivity("reservation", id, "출고등록", { 수량: maxQty }, { ...result, newId: res?.id }, `${result.수량}개 출고등록`);
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
        const canEditNote = e.target.dataset.canEditNote === "1";
        const result = await showNoteModal(current, canEditNote);
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

    // 다운로드 — 예약현황/타창고매출현황/전략단가/업데이트 탭이 열려 있으면 그
    // 탭의(검색/필터 적용된) 데이터를 내려받고, 아니면 기존대로 재고장 표
    // (state.filteredData)를 내려받는다(2026-08-18, 페이지 구분 대신 컨테이너
    // 표시 여부로 판단 — 업데이트 탭은 2026-08-20에 자체 다운로드 버튼을 없애고
    // 이 헤더 버튼 하나로 통합). 모바일에서는 exportTable이 같은 헤더/행 데이터를
    // CSV 대신 표 이미지로 내려받는다(양식은 엑셀과 동일, 파일 형식만 이미지).
    if (e.target.classList.contains("main-download-btn")) {
        const reservationsOpen = document.querySelector(".reservations-container")?.style.display === "";
        const salesOpen = document.querySelector(".sales-container")?.style.display === "";
        const priceOpen = document.querySelector(".price-container")?.style.display === "";
        const changesOpen = document.querySelector(".changes-container")?.style.display === "";

        if (changesOpen) {
            const headers = ["구분", "상품명", "브랜드", "등급", "ESTNO", "어제재고", "오늘재고", "BL", "창고"];
            const rows = getChangesTabRows().map(item => [
                item.changed_fields === "__NEW__" ? "신규" : "변경",
                item.상품명, item.브랜드, item.등급, item.ESTNO,
                item._prevQty, item.재고, item.BL, item.창고,
            ]);
            await exportTable("업데이트", headers, rows);
            return;
        }

        if (priceOpen) {
            const choice = await showPriceExportModal();
            if (!choice) return;
            const headers = ["분류", "브랜드", "품목", "등급/포장", "EST", "창고/비고", "평중"];
            if (choice.도매가) headers.push("도매가");
            if (choice.전략가) headers.push("전략가");
            const rows = state.filteredPrices.map(r => {
                const row = [r.분류, r.브랜드, r.품목, r["등급/포장"], r.EST, r["창고/비고"], r.평중 ?? ""];
                if (choice.도매가) row.push(r.도매가 ?? "");
                if (choice.전략가) row.push(r.전략가 ?? "");
                return row;
            });
            await exportTable("전략단가", headers, rows);
            return;
        }

        if (reservationsOpen || salesOpen) {
            if (salesOpen) {
                const headers = ["담당자", "상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "수량", "거래처", "비고", "단가", "중량", "총금액", "출고일", "상태"];
                const rows = state.filteredReservations.map(r => {
                    const unitPrice = parseUnitPrice(r.거래처);
                    const weight = parseWeight(r.거래처);
                    const total = (unitPrice !== null && weight !== null) ? Math.round(unitPrice * weight) : "";
                    // 내림(수량내림)된 행은 실제 DB 수량이 0이라 그대로 내려받으면 0으로
                    // 찍힘 — 화면 표시(qtyDisplay)와 동일하게 원수량으로 대체(2026-08-25).
                    const qty = r.수량내림 && r.원수량 ? r.원수량 : r.수량;
                    return [
                        r.담당자 || "", r.상품명, r.브랜드, r.등급, r.ESTNO, r.BL, r.창고, qty,
                        clientPrefix(r.거래처), r.비고 || "", unitPrice ?? "", weight ?? "",
                        total, r.출고일, r.status === "COMPLETED" ? "출고완료" : "",
                    ];
                });
                await exportTable("타창고매출현황", headers, rows);
            } else {
                const headers = ["담당자", "상품명", "브랜드", "등급", "ESTNO", "BL", "창고", "수량", "실재고", "가용재고", "거래처", "단가", "예약일", "출고일"];
                const rows = state.filteredReservations.map(r => [
                    r.담당자 || "", r.상품명, r.브랜드, r.등급, r.ESTNO, r.BL, r.창고, r.수량,
                    r.재고, r.가용재고 ?? "", clientPrefix(r.거래처), parseUnitPrice(r.거래처) ?? "", r.홀딩일자, r.출고일,
                ]);
                await exportTable("예약현황", headers, rows);
            }
            return;
        }

        const headers = ["상품명", "브랜드", "등급", "ESTNO", "재고", "예약", "가용", "BL", "창고", "유통기한", "평중", "비고"];
        const rows = state.filteredData.map(item => [
            item.상품명, item.브랜드, item.등급, item.ESTNO, item.재고,
            item.예약수량 || "", item.가용재고 ?? "", item.BL, item.창고,
            item.유통기한, item.평중, item.메모,
        ]);
        await exportTable("재고", headers, rows);
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
