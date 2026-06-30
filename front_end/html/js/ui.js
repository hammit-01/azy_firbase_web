export function showToast(msg, type = "success") {
    let t = document.getElementById("toast-msg");
    if (!t) {
        t = document.createElement("div");
        t.id = "toast-msg";
        document.body.appendChild(t);
    }
    t.className = "toast toast-" + type;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), type === "error" ? 3500 : 2200);
}

export function showError(msg) {
    showToast(msg, "error");
}

export function showConfirm(msg) {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        overlay.className = "confirm-overlay";
        overlay.innerHTML =
            `<div class="confirm-modal">` +
            `<p class="confirm-msg">${msg.replace(/\n/g, "<br>")}</p>` +
            `<div class="confirm-btns">` +
            `<button class="confirm-yes">확인</button>` +
            `<button class="confirm-no">취소</button>` +
            `</div></div>`;
        document.body.appendChild(overlay);

        overlay.querySelector(".confirm-yes").addEventListener("click", () => { overlay.remove(); resolve(true); });
        overlay.querySelector(".confirm-no").addEventListener("click", () => { overlay.remove(); resolve(false); });
        overlay.addEventListener("click", e => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
    });
}
