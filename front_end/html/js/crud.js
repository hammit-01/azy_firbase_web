// data update, delete, insert to firestore
import { updateItem, insertItem } from "./firestoreService.js";
import { doc, deleteDoc }  from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";
import { db } from "./firebase.js";

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
        // 기존 재고 차감(수정)
        await updateItem(item.id, {
            재고: remainQty
        });

        // 홀딩 행 추가
        const docRef = await insertItem({
            상품명: item.name,
            브랜드: item.brand,
            등급: item.grade || "",
            ESTNO: item.estNo || "",
            창고: item.warehouse,
            재고: holdQty,
            BL: item.bl,
            홀딩: note?.trim() || "",
            출고일: releaseDate || "",
            유통기한: item.dueDate || "",
            평중: item.weight || ""
        });

        console.log("홀딩 완료");

        return docRef.id;   // 새 문서 id 반환

    } catch (error) {
        console.error("업데이트 실패:", error);
        return null;
    }
}

export async function insertData(name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, frozen, unuse) {

    if (qty <= 0) {
        alert("입력 데이터를 확인해주세요.");
        return null;
    }

    try {
        // 행 추가
        const docRef = await insertItem({
            상품명: name, // not null
            브랜드: brand, // not null
            등급: grade || "",
            ESTNO: estNo || "",
            재고: qty, // not null
            BL: bl, // not null
            창고: warehouse, // not null
            유통기한: dueDate || "" || "",
            평중: weight, // not null
            출고일: releaseDate || "",
            홀딩: holding?.trim() || "",
            동결: frozen?.trim() || "",
            사용불가: unuse?.trim() || "",
        });

        console.log("추가 완료");

        return docRef.id;   // 새 문서 id 반환

    } catch (error) {
        console.error("업데이트 실패:", error);
        return null;
    }
}

export async function updateData(item, id, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, frozen, unuse) {

    const dataId = item ? item.id : id;

    const numQty = Number(qty);

    if (!numQty || numQty <= 0) {
        alert("수량을 확인해주세요.");
        return null;
    }

    const data = {
        상품명: name || "",
        브랜드: brand || "",
        등급: grade || "",
        ESTNO: estNo || "",
        재고: numQty,
        BL: bl || "",
        창고: warehouse || "",
        유통기한: dueDate || "",
        평중: Number(weight) || 0,
        출고일: releaseDate || "",
        홀딩: holding?.trim() || "",
        동결: frozen?.trim() || "",
        사용불가: unuse?.trim() || ""
    };

    try {
        await updateItem(dataId, data);

        console.log("수정 완료");

        return dataId;

    } catch (error) {
        console.error("수정 실패:", error);
        return null;
    }
}

export async function deleteItem(id) {
    try {
        await deleteDoc(doc(db, "all_data", id)); // 🔥 collection 이름 맞게 수정

        console.log("삭제 완료:", id);

    } catch (error) {
        console.error("삭제 실패:", error);
    }
}
