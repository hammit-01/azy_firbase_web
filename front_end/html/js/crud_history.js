import {
    updateItem, insertItem, moveHoldingToHistory, deleteItem as _deleteItem, cancelReservation,
    createReservation, updateReservation, reactivateReservation, toggleReservationRegister,
    createOutbound, updateOutbound, cancelOutbound,
    toggleOutboundComplete, toggleOutboundRegister,
    toggleOutboundSlip, toggleOutboundDeliveryCancel,
    createPrice, updatePrice, deletePrice,
} from "./firestoreService.js";
import { showToast, showError } from "./ui.js";
import { getStoredUser } from "./login.js";

const MAX_UNDO = 20;
const MAX_AGE_MS = 4 * 60 * 60 * 1000; // 4시간 후 만료

// 되돌리기 기록은 로그인한 사람 id별로 분리 — 같은 컴퓨터에서 다른 직원이 로그인해도
// 남의 작업을 실수로 되돌리는 일이 없도록
function _storageKey() {
    const user = getStoredUser();
    return user?.id ? `undo_stack_${user.id}` : "undo_stack_anon";
}

function _load() {
    try {
        const raw = JSON.parse(localStorage.getItem(_storageKey()) || "{}");
        if (!raw.ts || Date.now() - raw.ts > MAX_AGE_MS) return [];
        return Array.isArray(raw.stack) ? raw.stack : [];
    } catch { return []; }
}

function _save(stack) {
    try {
        localStorage.setItem(_storageKey(), JSON.stringify({ ts: Date.now(), stack: stack.slice(-MAX_UNDO) }));
    } catch {}
}

function _buildFn(desc) {
    switch (desc.type) {
        case "insert":
            return async () => _deleteItem(desc.newId);

        case "update":
            return async () => updateItem(desc.id, desc.prevData, desc.azy);

        case "holding":
            return async () => {
                if (desc.wasDeleted && desc.originalData) {
                    const { id: _id, updated_at: _ua, holdingTotal: _ht, holdingRecordId: _hri, ...restoreFields } = desc.originalData;
                    await insertItem({ ...restoreFields, 재고: desc.originalQty }, desc.azy);
                } else {
                    await updateItem(desc.originalId, { 재고: desc.originalQty }, desc.azy);
                }
                await _deleteItem(desc.holdingId, desc.azy);
                if (desc.holdingRecordId) await moveHoldingToHistory(desc.holdingRecordId, "취소", desc.azy);
            };

        case "reservation":
            return async () => cancelReservation(desc.id);

        case "bulk-reservation":
            return async () => { for (const id of desc.ids) await cancelReservation(id); };

        case "delete":
            return async () => insertItem(desc.restoreData, desc.azy);

        case "bulk-insert":
            return async () => { for (const id of desc.ids) await _deleteItem(id); };

        case "bulk-update":
            return async () => { for (const b of desc.backups) await updateItem(b.id, b.prevData, b.azy); };

        case "bulk-holding":
            return async () => {
                for (const b of desc.backups) {
                    if (b.wasDeleted && b.originalData) {
                        const { id: _id, updated_at: _ua, holdingTotal: _ht, holdingRecordId: _hri, ...restoreFields } = b.originalData;
                        await insertItem({ ...restoreFields, 재고: b.originalQty }, b.azy);
                    } else {
                        await updateItem(b.originalId, { 재고: b.originalQty }, b.azy);
                    }
                    await _deleteItem(b.holdingId, b.azy);
                    if (b.holdingRecordId) await moveHoldingToHistory(b.holdingRecordId, "취소", b.azy);
                }
            };

        case "bulk-delete":
            return async () => { for (const d of desc.items) await insertItem(d.data, d.azy); };

        // 예약/출고 현황 탭(2026-08-18) — 각 동작의 자연스러운 역동작으로 되돌린다.
        case "reservation-fields":
            return async () => updateReservation(desc.id, desc.prev);

        case "outbound-fields":
            return async () => updateOutbound(desc.id, desc.prev);

        case "reservation-note":
            return async () => updateReservation(desc.id, { 전달사항: desc.prevNote });

        case "outbound-note":
            return async () => updateOutbound(desc.id, { 전달사항: desc.prevNote });

        case "reservation-remark":
            return async () => updateReservation(desc.id, { 비고: desc.prevRemark });

        case "outbound-remark":
            return async () => updateOutbound(desc.id, { 비고: desc.prevRemark });

        // 출고등록(2026-08-24 재설계: outbound로 안 옮기고 출고일만 지정) 부분
        // 등록의 역동작 — 갈라져 나온 새 예약 행을 취소하고 원래 행 수량을 복구.
        case "outbound-register-split":
            return async () => {
                await cancelReservation(desc.newId);
                await updateReservation(desc.originalId, { 수량: desc.prevQty });
            };

        // 예약취소/출고취소의 역동작 = 취소 직전 스냅샷으로 다시 생성(같은 id는
        // 아니지만 같은 내용의 ACTIVE 행이 다시 생김 — "delete" 되돌리기와 동일 패턴)
        case "reservation-cancelled":
            return async () => createReservation(desc.product);

        case "outbound-cancelled":
            return async () => createOutbound(desc.product);

        // 출고완료/등록완료는 대칭 토글이라 한 번 더 누르면 그대로 원상복구
        case "outbound-toggle-complete":
            return async () => toggleOutboundComplete(desc.id);

        case "outbound-toggle-register":
            return async () => toggleOutboundRegister(desc.id, getStoredUser()?.이름 || "");

        // 익일 이후 출고 예정(미리보기) 행의 "수정중" 되돌리기(2026-08-26) — 대칭
        // 토글이라 한 번 더 누르면 원상복구.
        case "reservation-toggle-register":
            return async () => toggleReservationRegister(desc.id, getStoredUser()?.이름 || "");

        // 발주장(특판팀) 배송란 전표/취소 체크박스 — 대칭 토글이라 한 번 더
        // 누르면 그대로 원상복구(2026-08-26).
        case "outbound-toggle-slip":
            return async () => toggleOutboundSlip(desc.id);

        case "outbound-toggle-delivery-cancel":
            return async () => toggleOutboundDeliveryCancel(desc.id);

        // sales.html "추가"로 새로 만든 출고건 — 되돌리기 = 완전 삭제(원래 없던 행이라
        // 예약으로 되돌릴 대상 자체가 없음)
        case "outbound-created":
            return async () => cancelOutbound(desc.id, true);

        // 예약 현황 탭(비sales) "사용완료" 되돌리기(2026-08-18) — use_reservation은
        // 전량 사용 시 수량은 안 건드리고 status만 COMPLETED로 바꾸므로(수량 필드는
        // 그대로 남아있음) 그 경우 status만 ACTIVE로 되돌리면 되고, 부분 사용이면
        // 차감된 만큼 수량을 다시 더해주면 된다.
        case "reservation-used":
            return async () => {
                if (desc.wasFullUse) await reactivateReservation(desc.id);
                else await updateReservation(desc.id, { 수량: desc.prevQty });
            };

        // 전략단가 탭(2026-08-26) — 추가/수정/삭제의 자연스러운 역동작.
        case "price-insert":
            return async () => deletePrice(desc.newId);

        case "price-update":
            return async () => updatePrice(desc.id, desc.prevData);

        case "price-delete":
            return async () => createPrice(desc.restoreData);

        default:
            return null;
    }
}

export function pushUndo(descriptor) {
    const stack = _load();
    stack.push(descriptor);
    _save(stack);
}

export async function undoLastAction() {
    const stack = _load();
    const desc = stack.pop();
    _save(stack);

    if (!desc) {
        showError("되돌릴 작업이 없습니다.");
        return;
    }

    const fn = _buildFn(desc);
    if (!fn) {
        showError("알 수 없는 작업 유형입니다.");
        return;
    }

    try {
        await fn();
        showToast("✓ 되돌리기 완료");
    } catch (err) {
        console.error("되돌리기 실패:", err);
        showError("되돌리기 실패: " + err.message);
    }
}
