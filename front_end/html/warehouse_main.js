import { initFirebase, subscribeData } from "./js/firebase.js";
import { initDOM } from "./js/dom.js";
import { bindEvents } from "./js/events.js";

window.addEventListener("DOMContentLoaded", async () => {

    // Firebase 연결
    await initFirebase();

    // DOM 연결
    initDOM();

    // 이벤트 등록 (1번만)
    bindEvents();

    // Firestore 실시간 감시
    subscribeData();
});
