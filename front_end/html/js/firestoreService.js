import { db, handleQuotaExceeded } from "./firebase.js";

import {
  collection,
  addDoc,
  getDocs,
  doc,
  getDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  query,
  where,
  orderBy,
  onSnapshot
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

async function _wrap(fn) {
    try {
        return await fn();
    } catch (e) {
        const handled = await handleQuotaExceeded(e);
        if (!handled) throw e;
    }
}

// 추가
export async function insertItem(data) {
    return await _wrap(() => addDoc(collection(db, "all_data"), data));
}

// 홀딩 기록 추가 (자동 ID)
export async function insertHoldingRecord(data) {
    return await _wrap(() => addDoc(collection(db, "holding_data"), data));
}

// 홀딩 기록 추가 (지정 ID: {pk}hold01 형식)
export async function insertHoldingRecordWithId(holdId, data) {
    await _wrap(() => setDoc(doc(db, "holding_data", holdId), data));
    return { id: holdId };
}

// pk 기준 기존 홀딩 건수 조회 (다음 번호 결정용)
export async function getHoldingCountByPk(pk) {
    const q = query(collection(db, "holding_data"), where("pk", "==", pk));
    const snap = await _wrap(() => getDocs(q));
    return snap?.size ?? 0;
}

// holdingRecordId에서 원본 pk 추출 ({pk}hold01 → pk)
export function extractPkFromHoldingId(holdingRecordId) {
    if (!holdingRecordId) return null;
    return holdingRecordId.replace(/hold\d+$/, "");
}

// 홀딩 기록 수정
export async function updateHoldingRecord(id, data) {
    if (!id) return;
    await _wrap(() => updateDoc(doc(db, "holding_data", id), data));
}

// holding_data → holding_history 이동 (상태: "사용완료" | "취소")
export async function moveHoldingToHistory(id, status) {
    if (!id) return { historyId: null, originalData: null };
    const docRef = doc(db, "holding_data", id);
    const snap = await _wrap(() => getDoc(docRef));
    if (!snap?.exists()) return { historyId: null, originalData: null };

    const originalData = snap.data();
    const now = new Date().toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
    const historyRef = await _wrap(() => addDoc(collection(db, "holding_history"), {
        ...originalData,
        상태: status,
        처리일시: now
    }));
    await _wrap(() => deleteDoc(docRef));
    return { historyId: historyRef?.id ?? null, originalData };
}

// holding_history 삭제 (undo 시 사용)
export async function deleteHoldingHistory(id) {
    if (!id) return;
    await _wrap(() => deleteDoc(doc(db, "holding_history", id)));
}

// holding_data / all_data 특정 ID로 복구 (undo 시 사용)
export async function restoreDoc(collectionName, id, data) {
    await _wrap(() => setDoc(doc(db, collectionName, id), data));
}

// 수정
export async function updateItem(id, data) {
    await _wrap(() => updateDoc(doc(db, "all_data", id), data));
}

// 삭제
export async function deleteItem(id) {
    await _wrap(() => deleteDoc(doc(db, "all_data", id)));
}

// 조회 + 정렬
export function getItems(callback) {
    const q = query(
        collection(db, "all_data"),
        orderBy("상품명", "asc"),
        orderBy("브랜드", "asc"),
        orderBy("등급", "asc"),
        orderBy("창고", "asc"),
        orderBy("유통기한", "asc")
    );
    return onSnapshot(q, (snapshot) => {
        const items = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        callback(items);
    });
}
