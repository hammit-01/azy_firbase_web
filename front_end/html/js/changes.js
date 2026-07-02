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

    const issueItems   = _getIssueItems();
    const pendingItems = state.pendingChanges || [];

    if (issueItems.length === 0 && pendingItems.length === 0) {
        listEl.innerHTML = `<div class="changes-empty">확인할 변경사항 없음</div>`;
        return;
    }

    const issueHtml = issueItems.map(item => {
        const isOverQty = item.이상 === "수량초과";
        const orig  = item.원본재고 ?? 0;
        const holdId = item.holdingRecordId || "";
        return `
<div class="change-card ${isOverQty ? "over-qty" : "no-origin"}"
     data-id="${item.id}" data-hold-id="${holdId}" data-type="issue">
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
                   min="1" max="${orig}" value="${orig}" data-orig="${orig}">
            <button class="change-done-btn" disabled>완료</button>
        ` : `
            <button class="change-cancel-btn">홀딩 취소</button>
        `}
    </div>
</div>`;
    }).join("");

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

    listEl.innerHTML = pendingHtml + issueHtml;

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
    const count  = _getIssueItems().length + (state.pendingChanges?.length || 0);
    const badge  = document.querySelector(".changes-badge");
    const tabBtn = document.querySelector(".changes-tab-btn");
    if (!badge) return;
    badge.textContent   = count > 0 ? count : "";
    badge.style.display = count > 0 ? "inline-flex" : "none";
    tabBtn?.classList.toggle("has-issues", count > 0);
}
