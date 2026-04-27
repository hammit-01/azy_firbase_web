import { db } from "./firebase.js";
import {
  collection,
  addDoc,
  doc,
  updateDoc,
  deleteDoc
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

export async function insertItem(data) {
    await addDoc(collection(db, "all_data"), data);
}

export async function updateItem(id, data) {
    await updateDoc(doc(db, "all_data", id), data);
}

export async function deleteItem(id) {
    await deleteDoc(doc(db, "all_data", id));
}
