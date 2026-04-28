import { updateItem, insertItem } from "./firestoreService.js";

export async function holdingData(item, holdQty, holdDate, note) {
    console.log(item)
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
        재고수량: remainQty
    });

    const { id, ...newItem } = item;

    // data_eda 열 이름 기준으로 작성
    await insertItem({
        상품명: item.name,
        브랜드: item.brand,
        등급: item.grade || null,
        ESTNO: item.estno || null,
        창고: item.warehouse,
        재고수량: holdQty,
        BL번호: item.bl,
        홀딩: note?.trim() || null,
        출고예정일: holdDate || null,
        유통기한: item.dueday || null,
        평균중량: item.weight,
    });
}
