import { state } from "./state.js";
import { updateItem, updateHoldingRecord, moveHoldingToHistory, deleteItem, deletePendingChange } from "./firestoreService.js";
import { fetchAllData } from "./firebase.js";
import { showToast, showError, showConfirm } from "./ui.js";

export function renderChanges() {
    _updateBadge();

    const listEl = document.getElementById("changes-list");
    if (!listEl) return;

    const container = listEl.closest(".changes-container");
    if (!container || container.style.display === "none") return;

    const pendingItems = state.pendingChanges || [];

    if (pendingItems.length === 0) {
        listEl.innerHTML = `<div class="changes-empty">확인할 변경사항 없음</div>`;
        return;
    }

    const pendingHtml = pendingItems.map(p => {
        const diff    = Math.abs(p.diff || 0);
        const prevRaw = p.prev_raw ?? 0;
        const currRaw = p.curr_raw ?? 0;
        return `
<div class="change-card decrease-card"
     data-id="${p.id}" data-pk="${p.pk}"
     data-diff="${diff}" data-prev-nonhold="${p.prev_nonhold ?? 0}"
     data-type="pending">
    <div class="change-info">
        <span class="change-name">${p.상품명 || ""}</span>
        <span class="change-tag">${p.창고 || ""}</span>
        <span class="change-tag">${(p.BL || "").slice(-10)}</span>
        <span class="change-tag">${p.유통기한 || ""}</span>
        <span class="change-issue-badge badge-decrease">재고감소</span>
    </div>
    <div class="change-qty-row">
        <span>크롤 <strong>${prevRaw}</strong> → <strong>${currRaw}</strong>박스
              <span class="diff-label">(-${diff})</span></span>
    </div>
    <div class="change-qty-row">
        <span>non-hold <strong>${p.prev_nonhold ?? 0}</strong>박스 /
              hold <strong>${p.holdQty ?? 0}</strong>박스</span>
    </div>
    <div class="change-action">
        <button class="confirm-nonhold-btn">non-hold에서 차감</button>
        <button class="confirm-hold-btn">hold에서 차감</button>
    </div>
</div>`;
    }).join("");

    listEl.innerHTML = pendingHtml;

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
        // non-hold에서 차감 확인: 시스템이 이미 적용했으므로 pending 삭제만
        if (e.target.classList.contains("confirm-nonhold-btn")) {
            const card = e.target.closest(".change-card");
            const id   = card.dataset.id;
            try {
                await deletePendingChange(id);
                showToast("✓ non-hold 차감 확인 완료");
            } catch (err) {
                showError("처리 중 오류가 발생했습니다.");
            }
            return;
        }

        // hold에서 차감: non-hold 복구 + holding 행 감소
        if (e.target.classList.contains("confirm-hold-btn")) {
            const card       = e.target.closest(".change-card");
            const pk         = card.dataset.pk;
            const diff       = Number(card.dataset.diff);       // 감소량 (양수)
            const prevNonhold = Number(card.dataset.prevNonhold); // 복구할 non-hold 값

            if (!await showConfirm(`hold에서 ${diff}박스를 차감합니다.\n계속하시겠습니까?`)) return;

            try {
                // 1. 원본 행 non-hold 복구
                await updateItem(pk, { 재고: prevNonhold });

                // 2. holding 행에서 diff 차감 (state.allData 기준, 같은 pk 홀딩 행)
                const holdingRows = state.allData
                    .filter(d => d.pk === pk && d.상태 === "holding" && d.수집일 === "")
                    .sort((a, b) => (b.재고 || 0) - (a.재고 || 0));

                let remaining = diff;
                for (const hr of holdingRows) {
                    if (remaining <= 0) break;
                    const reduce  = Math.min(hr.재고 || 0, remaining);
                    const newQty  = (hr.재고 || 0) - reduce;
                    await updateItem(hr.id, { 재고: newQty });
                    if (hr.holdingRecordId)
                        await updateHoldingRecord(hr.holdingRecordId, { 수량: newQty });
                    remaining -= reduce;
                }

                await deletePendingChange(card.dataset.id);
                await fetchAllData();
                showToast("✓ hold 차감 완료");
            } catch (err) {
                console.error("hold 차감 실패:", err);
                showError("처리 중 오류가 발생했습니다.");
            }
            return;
        }

    });
}

function _updateBadge() {
    const count  = state.pendingChanges?.length || 0;
    const badge  = document.querySelector(".changes-badge");
    const tabBtn = document.querySelector(".changes-tab-btn");
    if (!badge) return;
    badge.textContent   = count > 0 ? count : "";
    badge.style.display = count > 0 ? "inline-flex" : "none";
    tabBtn?.classList.toggle("has-issues", count > 0);
}
