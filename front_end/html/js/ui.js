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

// 예약변경 모달 — 수량/출고일/거래처를 한 번에 수정(2026-08-14, "수량변경"에서 확장).
// current: {수량, 출고일, 거래처}. showPrice=true(sales.html)면 거래처 대신
// 거래처명(prefix)+단가+중량 입력칸 세 개로 나눠서 받는다 — 단가/중량은 자체
// 컬럼이 없어서 거래처 문자열에 "이름 숫자원 숫자kg"로 합쳐 저장하기 때문
// (table.js의 buildClientWithDetails와 짝). 저장 누르면 {수량, 출고일, 거래처}
// (showPrice면 {수량, 출고일, 거래처명, 단가, 중량}) 객체로 resolve, 취소/
// 바깥클릭이면 null.
export function showEditReservationModal(current, { showPrice = false } = {}) {
    return new Promise(resolve => {
        const clientFieldHtml = showPrice
            ? `<label>거래처명<input type="text" class="edit-res-client" value="${(current.거래처명 ?? "").replace(/"/g, "&quot;")}"></label>` +
              `<label>단가<input type="number" class="edit-res-price" min="0" value="${current.단가 ?? ""}"></label>` +
              `<label>중량(kg)<input type="number" step="0.01" min="0" class="edit-res-weight" value="${current.중량 ?? ""}"></label>`
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
            } else {
                result.거래처 = overlay.querySelector(".edit-res-client").value.trim();
            }
            close(result);
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
    });
}

// 출고등록 모달 — 예약 행에서 일부/전체 수량을 outbound로 옮길 때 사용재고(수량)/
// 출고일자/거래처를 입력받는다(2026-08-14). current: {수량}(예약의 현재 수량 =
// 입력 max/기본값). 저장 누르면 {수량, 출고일, 거래처} 객체로 resolve, 취소/
// 바깥클릭이면 null. 기존 edit-reservation-modal 스타일 재사용.
export function showRegisterOutboundModal(current) {
    return new Promise(resolve => {
        const maxQty = Number(current.수량) || 0;
        const today = new Date().toISOString().slice(0, 10);
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal edit-reservation-modal">` +
            `<p class="confirm-msg">출고등록</p>` +
            `<div class="edit-reservation-form">` +
            `<label>사용재고<input type="number" class="reg-ob-qty" min="1" max="${maxQty}" value="${maxQty}"></label>` +
            `<label>출고일<input type="date" class="reg-ob-date" value="${today}"></label>` +
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
            close({
                수량: qty,
                출고일: overlay.querySelector(".reg-ob-date").value,
                거래처: overlay.querySelector(".reg-ob-client").value.trim(),
            });
        });
        overlay.querySelector(".confirm-no").addEventListener("click", () => close(null));
        overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
    });
}

// 전달사항 모달 — 예약/출고 행의 "!" 버튼(2026-08-14). 보기/수정 겸용, 저장
// 누르면 새 문자열(빈 문자열이면 삭제)로 resolve, 취소/바깥클릭이면 null.
// 전달사항 팝업(2026-08-18 재설계) — 처음엔 보기 전용으로 뜨고(확인/수정),
// "수정"을 눌러야 텍스트박스 + 저장/취소가 나오는 2단계 흐름. 그냥 "!"만
// 눌러도 바로 편집 모드로 들어가던 전엔 실수로 고치기 쉬웠다는 피드백 반영.
export function showNoteModal(note) {
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
                `<button class="confirm-edit">수정</button>` +
                `<button class="confirm-yes">확인</button>` +
                `</div></div>`;
            overlay.querySelector(".confirm-edit").addEventListener("click", renderEdit);
            overlay.querySelector(".confirm-yes").addEventListener("click", () => close(null));
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

        overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
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
        overlay.addEventListener("click", e => { if (e.target === overlay) close(null); });
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
        overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
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

        overlay.querySelector(".confirm-yes").addEventListener("click", () => { overlay.remove(); resolve(true); });
        overlay.querySelector(".confirm-no").addEventListener("click", () => { overlay.remove(); resolve(false); });
        overlay.addEventListener("click", e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
    });
}
