// data update, delete, insert to firestore
import { updateItem, insertItem } from "./firestoreService.js";

export async function holdingData(item, holdQty, releaseDate, note) {

    const remainQty = item.qty - holdQty;

    if (remainQty < 0) {
        alert("수량이 부족합니다.");
        return null;
    }

    if (holdQty > item.qty) {
        alert("수량을 초과했습니다.");
        return null;
    }

    try {
        // 기존 재고 차감
        await updateItem(item.id, {
            재고: remainQty
        });

        // 홀딩 행 추가
        const docRef = await insertItem({
            상품명: item.name,
            브랜드: item.brand,
            등급: item.grade || null,
            ESTNO: item.estNo || null,
            창고: item.warehouse,
            재고: holdQty,
            BL: item.bl,
            홀딩: note?.trim() || null,
            출고일: releaseDate || null,
            유통기한: item.dueDate || null,
            평중: item.weight || null
        });

        console.log("홀딩 완료");

        return docRef.id;   // 새 문서 id 반환

    } catch (error) {
        console.error("업데이트 실패:", error);
        return null;
    }
}
