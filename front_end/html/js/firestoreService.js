// firestoreService.js — MySQL API 버전
import {
    apiInsertItem, apiUpdateItem, apiDeleteItem,
    apiInsertHoldingRecord, apiUpdateHoldingRecord, apiDeleteHoldingRecord,
    apiGetHoldingCount, apiFetch,
} from "./api.js";

// 추가
export async function insertItem(data, azy) {
    return await apiInsertItem(data, azy);
}

// 홀딩 기록 추가 (지정 ID)
export async function insertHoldingRecordWithId(holdId, data, azy) {
    await apiInsertHoldingRecord(holdId, data, azy);
    return { id: holdId };
}

// pk 기준 기존 홀딩 건수 조회
export async function getHoldingCountByPk(pk, azy) {
    return await apiGetHoldingCount(pk, azy);
}

// holdingRecordId에서 원본 pk 추출
export function extractPkFromHoldingId(holdingRecordId) {
    if (!holdingRecordId) return null;
    return holdingRecordId.replace(/hold\d+$/, "");
}

// 홀딩 기록 수정
export async function updateHoldingRecord(id, data, azy) {
    if (!id) return;
    await apiUpdateHoldingRecord(id, data, azy);
}

// holding_records 삭제 (MySQL 버전에서는 history 이동 없이 삭제)
export async function moveHoldingToHistory(id, status, azy) {
    if (!id) return { historyId: null, originalData: null };
    try {
        const r = await apiFetch(`/api/holding_records_detail/${encodeURIComponent(id)}`, {}, azy);
        const originalData = r.data;
        await apiDeleteHoldingRecord(id, azy);
        return { historyId: null, originalData };
    } catch {
        await apiDeleteHoldingRecord(id, azy);
        return { historyId: null, originalData: null };
    }
}

// 수정
export async function updateItem(id, data, azy) {
    await apiUpdateItem(id, data, azy);
}

// 삭제
export async function deleteItem(id, azy) {
    await apiDeleteItem(id, azy);
}
