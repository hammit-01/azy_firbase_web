import { doc, updateDoc } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";

export function bindHoldingEvents(db, selectedItems, renderTable, renderPanel) {

    document.addEventListener("click", async (e) => {

        if (!e.target.classList.contains("hold-btn")) return;

        const key = e.target.dataset.key;
        const parent = e.target.closest(".selected-item");

        const holding = parent.querySelector(".holding_int")?.value || "";
        const date = parent.querySelector(".holding_date")?.value || "";
        const memo = parent.querySelector(".holding_text")?.value || "";

        try {
            await updateDoc(doc(db, "all_data", key), {
                홀딩: holding,
                홀딩일: date,
                비고: memo
            });

            const old = selectedItems.get(key);

            if (old) {
                selectedItems.set(key, {
                    ...old,
                    holding,
                    date,
                    memo
                });
            }

            renderTable();
            renderPanel();

        } catch (err) {
            console.error("홀딩 저장 실패:", err);
        }
    });


    // 선택 전체 취소도 같이 관리 (선택)
    window.clearSelection = function () {

        selectedItems.clear();

        document.querySelectorAll(".row-check").forEach(c => c.checked = false);
        document.querySelectorAll(".selected-row").forEach(r => r.classList.remove("selected-row"));

        renderTable();
        renderPanel();
    };
}
