import { db } from "./firebase.js";

import {
  collection,
  addDoc,
  doc,
  getDoc,
  updateDoc,
  deleteDoc,
  query,
  orderBy,
  onSnapshot
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";


// 추가
export async function insertItem(data) {
    return await addDoc(collection(db, "all_data"), data);
}

// 홀딩 기록 추가
export async function insertHoldingRecord(data) {
    return await addDoc(collection(db, "holding_data"), data);
}

// holding_data → holding_history 이동 (상태: "사용완료" | "취소")
export async function moveHoldingToHistory(id, status) {
    if (!id) return;
    const docRef = doc(db, "holding_data", id);
    const snap = await getDoc(docRef);
    if (!snap.exists()) return;

    const now = new Date().toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
    await addDoc(collection(db, "holding_history"), {
        ...snap.data(),
        상태: status,
        처리일시: now
    });
    await deleteDoc(docRef);
}


// 수정
export async function updateItem(id, data) {
    await updateDoc(doc(db, "all_data", id), data);
}


// 삭제
export async function deleteItem(id) {
    await deleteDoc(doc(db, "all_data", id));
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

        const items = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));

        callback(items);
    });
}