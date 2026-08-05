import { updateItem, insertItem, updateHoldingRecord, moveHoldingToHistory, deleteItem as _deleteItem, createReservation } from "./firestoreService.js";
import { fetchAllData } from "./firebase.js";
import { pushUndo } from "./crud_history.js";
import { showError } from "./ui.js";
import { getStoredUser } from "./login.js";
import { apiLogChange } from "./api.js";

function _logChange(azy, targetId, action) {
    apiLogChange(getStoredUser()?.id, azy ? "azy_inventory" : "inventory", targetId, action);
}

// item은 정규화된 형태(.raw._source/._rawId) 또는 raw 형태(._source/._rawId) 둘 다 올 수 있다.
function _isAzy(item) {
    return (item?._source ?? item?.raw?._source) === "azy";
}
function _rawId(item) {
    return item?._rawId ?? item?.raw?._rawId ?? item?.id;
}

// 실재고/예약 분리 재설계(2026-08-05) — 예약은 소스 재고(item)를 전혀 건드리지 않는다.
// weight 인자는 옛 모델(홀딩 전용 행에 평중을 따로 저장)의 흔적으로, 새 모델에선 예약이
// 별도 행을 만들지 않아 의미가 없어져 받기만 하고 안 쓴다(호출부 시그니처 유지 목적).
export async function holdingData(item, holdQty, releaseDate, note, memo = "", weight = null, noUndo = false) {

    if (!holdQty || holdQty <= 0) {
        showError("예약 수량을 1 이상 입력해주세요.");
        return null;
    }

    const azy = _isAzy(item);
    const rawId = _rawId(item);

    try {
        const rec = await createReservation({
            상품명: item.name,
            브랜드: item.brand || "",
            등급:   item.grade || "",
            ESTNO:  item.estNo || "",
            BL:     item.bl,
            창고:   item.warehouse,
            수량:   holdQty,
            거래처: memo || item.memo || "",
            담당자: note?.trim() || "",
            출고일: releaseDate || "",
        });

        if (!noUndo) pushUndo({ type: "reservation", id: rec.id });

        _logChange(azy, rawId, "예약");

        await fetchAllData();
        return { reservationId: rec.id, azy };

    } catch (error) {
        console.error("예약 실패:", error);
        showError(error.message || "예약에 실패했습니다.");
        return null;
    }
}

export async function insertData(
    name, brand, grade, estNo, qty, bl, warehouse,
    dueDate, weight, releaseDate, holding, dataState, memo,
    noUndo = false
) {

    if (qty <= 0) {
        showError("입력 데이터를 확인해주세요.");
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

        if (!noUndo) pushUndo({ type: "insert", newId: docRef.id });

        _logChange(window.__AZY_API_MODE, docRef.id, "삽입");

        await fetchAllData();
        return docRef.id;

    } catch (error) {
        console.error("업데이트 실패:", error);
        return null;
    }
}

export async function updateData(item, id, name, brand, grade, estNo, qty, bl, warehouse, dueDate, weight,
    releaseDate, holding, dataState, memo, noUndo = false) {

    const azy = _isAzy(item);
    const rawId = item ? _rawId(item) : id;
    const uiId = item ? item.id : id;

    const numQty = Number(qty);

    // 정규화(normalized) 또는 raw Firestore 필드 모두 지원
    const prevData = {
        상품명: item.name  || item["상품명"]  || "",
        브랜드: item.brand || item["브랜드"]  || "",
        등급:   item.grade || item["등급"]    || "",
        ESTNO:  item.estNo || item["ESTNO"]   || "",
        재고:   item.qty   ?? item["재고"]    ?? 0,
        BL:     item.bl    || item["BL"]      || "",
        창고:   item.warehouse || item["창고"] || "",
        유통기한: item.dueDate  || item["유통기한"] || "",
        평중:   item.weight    ?? item["평중"]    ?? 0,
        출고일: item.releaseDate || item["출고일"] || "",
        홀딩:   item.holding   || item["홀딩"]   || "",
        상태:   item.dataState || item["상태"]   || "",
        메모:   item.memo      || item["메모"]   || ""
    };

    if (!numQty || numQty <= 0) {
        showError("수량을 확인해주세요.");
        return null;
    }

    const resolvedState = dataState?.trim() || "";

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
        상태: resolvedState,
        메모: memo || ""
    };

    // 변경 사항 없으면 스킵
    const noChange = Object.keys(data).every(k => String(data[k]) === String(prevData[k] ?? ""));
    if (noChange) {
        showError("변경된 내용이 없습니다.");
        return null;
    }

    try {

        await updateItem(rawId, data, azy);

        const holdingRecordId = item?.raw?.holdingRecordId;
        const wasHolding = item?.dataState === "holding";

        if (wasHolding && resolvedState !== "holding") {
            await moveHoldingToHistory(holdingRecordId, "취소", azy);
        } else if (resolvedState === "holding" && holdingRecordId) {
            await updateHoldingRecord(holdingRecordId, {
                홀딩:   holding?.trim() || "",
                출고일: releaseDate || "",
                메모:   memo || ""
            }, azy);
        }

        if (!noUndo) pushUndo({ type: "update", id: rawId, prevData, azy });

        _logChange(azy, rawId, "수정");

        await fetchAllData();
        return {
            id: uiId,
            rawId,
            azy,
            prevData
        };

    } catch (error) {
        console.error("수정 실패:", error);
        return null;
    }
}

export async function deleteItem(item, noUndo = false, noFetch = false) {
    const azy = _isAzy(item);
    const rawId = _rawId(item);
    try {
        if (!noUndo) {
            const { id: _id, _source: _s, _rawId: _r, ...restoreData } = { ...item };
            pushUndo({ type: "delete", restoreData, azy });
        }
        await _deleteItem(rawId, azy);
        _logChange(azy, rawId, "삭제");
        if (!noFetch) await fetchAllData();
    } catch (error) {
        console.error("삭제 실패:", error);
    }
}
