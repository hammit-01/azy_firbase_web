import { updateItem, insertItem, insertHoldingRecord } from "./firestoreService.js";
import { doc, deleteDoc } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-firestore.js";
import { db } from "./firebase.js";

export async function holdingData(item, holdQty, releaseDate, note, memo = "") {

    const remainQty = item.qty - holdQty;

    if (remainQty < 0) {
        alert("수량이 부족합니다.");
        return null;
    }

    try {

        // 기존 재고 차감
        await updateItem(item.id, {
            재고: remainQty
        });

        // all_data에 홀딩 row 추가
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
            평중: item.weight || "",
            상태: "holding",
            메모: memo || item.memo || ""
        });

        // holding_data 테이블에 홀딩 정보 기록
        const pk = item.raw?.pk || item.id;
        const holdRef = await insertHoldingRecord({
            pk:    pk,
            수량:  holdQty,
            홀딩:  note?.trim() || "",
            출고일: releaseDate || "",
            메모:  memo || item.memo || ""
        });

        return {
            originalId:      item.id,
            originalQty:     item.qty,
            holdingId:       docRef.id,
            holdingRecordId: holdRef.id
        };

    } catch (error) {

        console.error("업데이트 실패:", error);

        return null;
    }
}

export async function insertData(
    name,
    brand,
    grade,
    estNo,
    qty,
    bl,
    warehouse,
    dueDate,
    weight,
    releaseDate,
    holding,
    dataState,
    memo
) {

    if (qty <= 0) {
        alert("입력 데이터를 확인해주세요.");
        return null;
    }

    try {

        const docRef = await insertItem({

            상품명: name,
            브랜드: brand,
            등급: grade || "",
            ESTNO: estNo || "",
            재고: qty,
            BL: bl,
            창고: warehouse,
            유통기한: dueDate || "",
            평중: weight,
            출고일: releaseDate || "",
            홀딩: holding?.trim() || "",
            상태: dataState?.trim() || "",
            메모: memo || ""

        });


        return docRef.id;

    } catch (error) {

        console.error("업데이트 실패:", error);

        return null;
    }
}

export async function updateData(item, id, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, dataState, memo) {

    const dataId = item ? item.id : id;

    const numQty = Number(qty);

    const prevData = {
        상품명: item.name || "",
        브랜드: item.brand || "",
        등급: item.grade || "",
        ESTNO: item.estNo || "",
        재고: item.qty || 0,
        BL: item.bl || "",
        창고: item.warehouse || "",
        유통기한: item.dueDate || "",
        평중: item.weight || 0,
        출고일: item.releaseDate || "",
        홀딩: item.holding || "",
        상태: item.dataState || "",
        메모: item.memo || ""
    };

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
        상태: dataState?.trim() || "",
        메모: memo || ""
    };

    try {

        await updateItem(dataId, data);


        return {
            id: dataId,
            prevData
        };

    } catch (error) {

        console.error("수정 실패:", error);

        return null;
    }
}

export async function deleteItem(item) {
    try {
        await deleteDoc(doc(db, "all_data", item.id)); // 🔥 collection 이름 맞게 수정


    } catch (error) {
        console.error("삭제 실패:", error);
    }
}
