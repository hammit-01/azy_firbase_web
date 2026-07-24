import { updateItem, insertItem, insertHoldingRecordWithId, getHoldingCountByPk, updateHoldingRecord, moveHoldingToHistory, deleteItem as _deleteItem } from "./firestoreService.js";
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

export async function holdingData(item, holdQty, releaseDate, note, memo = "", weight = null, noUndo = false) {

    if (!holdQty || holdQty <= 0) {
        showError("홀딩 수량을 1 이상 입력해주세요.");
        return null;
    }

    const remainQty = item.qty - holdQty;

    if (remainQty < 0) {
        showError("수량이 부족합니다.");
        return null;
    }

    const azy = _isAzy(item);
    const rawId = _rawId(item);

    try {

        // 전량 홀딩이면 0박스 행이 남지 않도록 삭제, 부분 홀딩이면 차감
        if (remainQty === 0) {
            await _deleteItem(rawId, azy);
        } else {
            await updateItem(rawId, { 재고: remainQty }, azy);
        }

        // 1. holding_data 생성
        //    전량 홀딩(remainQty=0): holdId = pk 그대로
        //    부분 홀딩(remainQty>0): holdId = {pk}hold01, hold02, ...
        const pk = item.raw?.pk || rawId;
        let holdId;
        if (remainQty === 0) {
            holdId = pk;
        } else {
            const count = await getHoldingCountByPk(pk, azy);
            holdId = `${pk}hold${String(count + 1).padStart(2, "0")}`;
        }
        const holdRef = await insertHoldingRecordWithId(holdId, {
            pk:     pk,
            BL:     item.bl    || "",
            ESTNO:  item.estNo || "",
            등급:   item.grade  || "",
            수량:   holdQty,
            홀딩:   note?.trim() || "",
            출고일: releaseDate || "",
            메모:   memo || item.memo || "",
            uid:    getStoredUser()?.id || ""
        }, azy);

        // 2. all_data에 홀딩 row 추가 (테이블 표시용 필드 포함)
        // 수집일: "" → updater.py의 where(수집일 == "") 쿼리로 홀딩 row 식별 가능
        const docRef = await insertItem({
            pk:              pk,
            상품명:          item.name,
            브랜드:          item.brand,
            등급:            item.grade || "",
            ESTNO:           item.estNo || "",
            창고:            item.warehouse,
            재고:            holdQty,
            BL:              item.bl,
            홀딩:            note?.trim() || "",
            출고일:          releaseDate || "",
            유통기한:        item.dueDate || "",
            평중:            weight !== null ? Number(weight) : (item.weight || ""),
            메모:            memo || item.memo || "",
            상태:            "holding",
            수집일:          "",
            holdingRecordId: holdRef.id
        }, azy);

        // 전량 홀딩은 원본 row가 삭제되므로 undo 시 재삽입할 수 있도록 원본 데이터 보존
        const wasDeleted = remainQty === 0;
        const { _source: _s, _rawId: _r, ...originalDataClean } = item.raw || {};
        const originalData = wasDeleted ? { ...originalDataClean, 재고: item.qty } : null;

        if (!noUndo) pushUndo({
            type:            "holding",
            originalId:      rawId,
            originalQty:     item.qty,
            wasDeleted,
            originalData,
            holdingId:       docRef.id,
            holdingRecordId: holdRef.id,
            azy
        });

        _logChange(azy, rawId, "홀딩");

        await fetchAllData();
        return {
            originalId:      rawId,
            originalQty:     item.qty,
            wasDeleted,
            originalData,
            holdingId:       docRef.id,
            holdingRecordId: holdRef.id,
            azy
        };

    } catch (error) {
        console.error("업데이트 실패:", error);
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
