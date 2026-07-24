import { updateItem, insertItem, moveHoldingToHistory, deleteItem as _deleteItem } from "./firestoreService.js";
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
