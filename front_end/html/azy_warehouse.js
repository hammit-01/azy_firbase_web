import { initFirebase, subscribeData, loadEmployees } from "./js/firebase.js";
import { initDOM } from "./js/dom.js";
import { bindEvents } from "./js/events.js";

window.addEventListener("DOMContentLoaded", async () => {
    await initFirebase();
    initDOM();
    bindEvents();
    loadEmployees();
    subscribeData();
});
