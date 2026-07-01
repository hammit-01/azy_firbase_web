import { state } from "./state.js";
import { updateItem, updateHoldingRecord, moveHoldingToHistory, deleteItem } from "./firestoreService.js";
import { fetchAllData } from "./firebase.js";
import { showToast, showError, showConfirm } from "./ui.js";

export function renderChanges() {
    _updateBadge();

    const listEl = document.getElementById("changes-list");
    if (!listEl) return;

    // 탭이 숨겨져 있으면 배지만 업데이트
    const container = listEl.closest(".changes-container");
    if (!container || container.style.display === "none") return;

    const items = _getIssueItems();

    if (items.length === 0) {
        listEl.innerHTML = `<div class="changes-empty">이상 홀딩 없음</div>`;
        return;
    }

    listEl.innerHTML = items.map(item => {
        const isOverQty = item.이상 === "수량초과";
        const orig = item.원본재고 ?? 0;
        const holdId = item.holdingRecordId || "";
        return `
<div class="change-card ${isOverQty ? "over-qty" : "no-origin"}"
     data-id="${item.id}" data-hold-id="${holdId}">
    <div class="change-info">
        <span class="change-name">${item.상품명 || ""}</span>
        <span class="change-tag">${item.창고 || ""}</span>
        <span class="change-tag">${(item.BL || "").slice(-10)}</span>
        <span class="change-tag">${item.유통기한 || ""}</span>
        <span class="change-issue-badge ${isOverQty ? "badge-over" : "badge-none"}">
            ${isOverQty ? "수량초과" : "원본없음"}
        </span>
    </div>
    <div class="change-qty-row">
        <span>홀딩 <strong>${item.재고}</strong>박스</span>
        ${isOverQty
            ? `<span class="arrow-sep">→</span>
               <span>원본재고 <strong>${orig}</strong>박스</span>`
            : `<span class="no-origin-text">창고에서 사라진 항목</span>`
        }
    </div>
    <div class="change-action">
        ${isOverQty ? `
            <label class="change-qty-label">수정 수량</label>
            <input type="number" class="change-qty-input"
                   min="1" max="${orig}" value="${orig}"
                   data-orig="${orig}">
            <button class="change-done-btn" disabled>완료</button>
        ` : `
            <button class="change-cancel-btn">홀딩 취소</button>
        `}
    </div>
</div>`;
    }).join("");

    // input → 완료 버튼 활성화 연동
    listEl.querySelectorAll(".change-qty-input").forEach(input => {
        const sync = () => {
            const card = input.closest(".change-card");
            const btn  = card.querySelector(".change-done-btn");
            const orig = Number(input.dataset.orig);
            const val  = Number(input.value);
            btn.disabled = !(val >= 1 && val <= orig);
        };
        input.addEventListener("input", sync);
        sync();
    });
}

export function bindChangesEvents() {
    document.getElementById("changes-list")?.addEventListener("click", async (e) => {
        // 완료: 홀딩 수량을 원본재고 이하로 수정
        if (e.target.classList.contains("change-done-btn")) {
            const card   = e.target.closest(".change-card");
            const id     = card.dataset.id;
            const holdId = card.dataset.holdId;
            const newQty = Number(card.querySelector(".change-qty-input").value);

            try {
                await updateItem(id, { 재고: newQty, 이상: "", 원본재고: "" });
                if (holdId) await updateHoldingRecord(holdId, { 수량: newQty });
                showToast("✓ 수량 수정 완료 — 다음 파이프라인 실행 시 원본 자동 반영");
                await fetchAllData();
            } catch (err) {
                console.error("변경 처리 실패:", err);
                showError("처리 중 오류가 발생했습니다.");
            }
            return;
        }

        // 홀딩 취소: 원본없음 항목 보관 이력으로 이동
        if (e.target.classList.contains("change-cancel-btn")) {
            if (!await showConfirm("홀딩을 취소합니다.\n계속하시겠습니까?")) return;

            const card   = e.target.closest(".change-card");
            const id     = card.dataset.id;
            const holdId = card.dataset.holdId;

            try {
                if (holdId) await moveHoldingToHistory(holdId, "취소");
                await deleteItem(id);
                showToast("✓ 홀딩 취소 완료");
                await fetchAllData();
            } catch (err) {
                console.error("홀딩 취소 실패:", err);
                showError("처리 중 오류가 발생했습니다.");
            }
            return;
        }
    });
}

function _getIssueItems() {
    return state.allData.filter(d =>
        d.상태 === "holding" && d.이상 && d.이상 !== ""
    );
}

function _updateBadge() {
    const count  = _getIssueItems().length;
    const badge  = document.querySelector(".changes-badge");
    const tabBtn = document.querySelector(".changes-tab-btn");
    if (!badge) return;
    badge.textContent  = count > 0 ? count : "";
    badge.style.display = count > 0 ? "inline-flex" : "none";
    tabBtn?.classList.toggle("has-issues", count > 0);
}
