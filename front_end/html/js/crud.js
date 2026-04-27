import { updateItem, insertItem } from "./firestoreService.js";

export async function holdingData(item, holdQty, holdDate, note) {
    console.log(item.id)
    const remainQty = item.qty - holdQty;

    if (remainQty < 0) {
        alert("수량이 부족합니다.");
        return;
    }

    if (holdQty > item.qty) {
        alert("수량을 초과했습니다.");
        return;
    }

    await updateItem(item.id, {
        qty: remainQty
    });

    const { id, ...newItem } = item;

    // data_eda 열 이름 기준으로 작성
    await insertItem({
        ...newItem,
        qty: holdQty,
        holing: true,
        stockDate: holdDate || null,
        notes: note?.trim() || ""
    });
}
