import { db } from "./firebase.js";

import {
  collection,
  addDoc,
  doc,
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

// 홀딩 기록 삭제
export async function deleteHoldingRecord(id) {
    await deleteDoc(doc(db, "holding_data", id));
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