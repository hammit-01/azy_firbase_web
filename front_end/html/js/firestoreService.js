// firestoreService.js — MySQL API 버전
import {
    apiInsertItem, apiUpdateItem, apiDeleteItem,
    apiUpdateHoldingRecord, apiDeleteHoldingRecord, apiFetch,
    apiCreateReservation, apiCancelReservation, apiCompleteReservation, apiUseReservation,
    apiReactivateReservation,
    apiUpdateReservation, apiRegisterOutboundFromReservation,
    apiGetReservationsByPk, apiGetAllReservations,
    apiGetAllOutbound, apiCreateOutbound, apiUpdateOutbound, apiCancelOutbound, apiUseOutbound,
    apiToggleOutboundComplete, apiToggleOutboundRegister,
    apiGetAllPrices, apiCreatePrice, apiUpdatePrice, apiDeletePrice,
} from "./api.js";

// 예약 생성/취소/완료 — 실재고와 완전히 분리된 새 모델(2026-08-05).
// product: {상품명, 브랜드, 등급, ESTNO, BL, 창고, 수량, 거래처, 담당자, 출고일}
export async function createReservation(product) {
    return apiCreateReservation(product);
}
export async function cancelReservation(id) {
    return apiCancelReservation(id);
}
export async function completeReservation(id) {
    return apiCompleteReservation(id);
}
export async function useReservation(id, qty) {
    return apiUseReservation(id, qty);
}
export async function reactivateReservation(id) {
    return apiReactivateReservation(id);
}
export async function updateReservation(id, fields) {
    return apiUpdateReservation(id, fields);
}
export async function registerOutboundFromReservation(id, fields) {
    return apiRegisterOutboundFromReservation(id, fields);
}
export async function getReservationsByPk(pk) {
    return apiGetReservationsByPk(pk);
}
export async function getAllReservations() {
    return apiGetAllReservations();
}

// outbound(타창고매출현황) — 예약과 분리된 별도 저장소(2026-08-14)
export async function getAllOutbound() {
    return apiGetAllOutbound();
}
export async function createOutbound(product) {
    return apiCreateOutbound(product);
}
export async function updateOutbound(id, fields) {
    return apiUpdateOutbound(id, fields);
}
export async function cancelOutbound(id, deleteIt = false) {
    return apiCancelOutbound(id, deleteIt);
}
export async function useOutbound(id, qty) {
    return apiUseOutbound(id, qty);
}
export async function toggleOutboundComplete(id) {
    return apiToggleOutboundComplete(id);
}
export async function toggleOutboundRegister(id) {
    return apiToggleOutboundRegister(id);
}

// 추가
export async function insertItem(data, azy) {
    return await apiInsertItem(data, azy);
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

// 전략단가(price, 2026-08-19)
export async function getAllPrices() {
    return apiGetAllPrices();
}
export async function createPrice(row) {
    return apiCreatePrice(row);
}
export async function updatePrice(id, fields) {
    return apiUpdatePrice(id, fields);
}
export async function deletePrice(id) {
    return apiDeletePrice(id);
}
