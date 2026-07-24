import { initFirebase, subscribeData, loadEmployees } from "./js/firebase.js";
import { initDOM } from "./js/dom.js";
import { bindEvents } from "./js/events.js";
import { initLogin } from "./js/login.js";

window.addEventListener("DOMContentLoaded", async () => {

    // Firebase 연결
    await initFirebase();

    // DOM 연결
    initDOM();

    // 이벤트 등록
    bindEvents();
    initLogin();

    // 직원 목록 + Firestore 동시 시작 (병렬)
    loadEmployees();
    subscribeData();
});
