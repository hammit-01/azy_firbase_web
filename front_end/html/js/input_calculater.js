export function calculateTotal() {

    let total = 0;

    document.querySelectorAll(".hold-qty").forEach(input => {
        total += Number(parseFloat(input.value).toFixed(2)) || 0;
    });

    return total; // 🔥 무조건 반환
}

