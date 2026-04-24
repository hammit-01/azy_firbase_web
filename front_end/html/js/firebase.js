import { initializeApp }
from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";

import {
    getFirestore,
    collection,
    onSnapshot
}
from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

import { state } from "./state.js";
import { renderTable } from "./table.js";
import { renderPanel } from "./panel.js";

export let db;

export async function initFirebase() {
    const firebaseConfig = {
        apiKey: "AIza...",
        authDomain: "azy7503-d80d9.firebaseapp.com",
        projectId: "azy7503-d80d9"
    };

    const app = initializeApp(firebaseConfig);
    db = getFirestore(app);

    return db;
}


export function subscribeData() {

    onSnapshot(collection(db, "all_data"), (snapshot) => {

        state.allData = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));

        renderTable();
        renderPanel();
    });
}
