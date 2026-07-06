import { updateItem, insertItem, moveHoldingToHistory, deleteItem as _deleteItem } from "./firestoreService.js";
import { showToast, showError } from "./ui.js";

const STORAGE_KEY = "undo_stack";
const MAX_UNDO = 20;
const MAX_AGE_MS = 4 * 60 * 60 * 1000; // 4시간 후 만료

function _load() {
    try {
        const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
        if (!raw.ts || Date.now() - raw.ts > MAX_AGE_MS) return [];
        return Array.isArray(raw.stack) ? raw.stack : [];
    } catch { return []; }
}

function _save(stack) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ ts: Date.now(), stack: stack.slice(-MAX_UNDO) }));
    } catch {}
}

function _buildFn(desc) {
    switch (desc.type) {
        case "insert":
            return async () => _deleteItem(desc.newId);

        case "update":
            return async () => updateItem(desc.id, desc.prevData);

        case "holding":
            return async () => {
                if (desc.wasDeleted && desc.originalData) {
                    const { id: _id, updated_at: _ua, holdingTotal: _ht, holdingRecordId: _hri, ...restoreFields } = desc.originalData;
                    await insertItem({ ...restoreFields, 재고: desc.originalQty });
                } else {
                    await updateItem(desc.originalId, { 재고: desc.originalQty });
                }
                await _deleteItem(desc.holdingId);
                if (desc.holdingRecordId) await moveHoldingToHistory(desc.holdingRecordId, "취소");
            };

        case "delete":
            return async () => insertItem(desc.restoreData);

        case "bulk-insert":
            return async () => { for (const id of desc.ids) await _deleteItem(id); };

        case "bulk-update":
            return async () => { for (const b of desc.backups) await updateItem(b.id, b.prevData); };

        case "bulk-holding":
            return async () => {
                for (const b of desc.backups) {
                    if (b.wasDeleted && b.originalData) {
                        const { id: _id, updated_at: _ua, holdingTotal: _ht, holdingRecordId: _hri, ...restoreFields } = b.originalData;
                        await insertItem({ ...restoreFields, 재고: b.originalQty });
                    } else {
                        await updateItem(b.originalId, { 재고: b.originalQty });
                    }
                    await _deleteItem(b.holdingId);
                    if (b.holdingRecordId) await moveHoldingToHistory(b.holdingRecordId, "취소");
                }
            };

        case "bulk-delete":
            return async () => { for (const d of desc.items) await insertItem(d); };

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
