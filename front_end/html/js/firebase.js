import { initializeApp }
from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";

import {
    getFirestore,
    collection,
    getDocs,
    onSnapshot
}
from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderSelectData } from "./panel.js";

export let db;

export async function initFirebase() {
    const firebaseConfig = {
        apiKey: "AIzaSyBMzVr396MMhlAEwsOfMhVLrOMnRMfWkgQ",
        authDomain: "azy7503-d80d9.firebaseapp.com",
        projectId: "azy7503-d80d9"
    };

    const app = initializeApp(firebaseConfig);
    db = getFirestore(app);

    return db;
}


export async function loadEmployees() {
    const snap = await getDocs(collection(db, "employees"));
    state.employees = snap.docs
        .map(d => d.data())
        .sort((a, b) => a["이름"].localeCompare(b["이름"], "ko"));
}

export function subscribeData() {

    onSnapshot(collection(db, "all_data"), (snapshot) => {

        state.allData = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));

        renderTable();
        renderSelectData();
    });
}
