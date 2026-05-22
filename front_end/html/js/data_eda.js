// data_eda.js
// Firebase raw data -> UI friendly normalized data layer

/**
 * raw Firebase 데이터를 UI에서 쓰기 좋게 변환 (EDA: Extract, Deduplicate, Adapt)
 */
export function normalizeItem(raw) {
    if (!raw) return "";

    return {
        id: raw.id ?? raw._id ?? "",

        name: raw.상품명 ?? raw.name ?? raw.itemName ?? "",
        brand: raw.브랜드 ?? "",
        grade: raw.등급 ?? "",
        estNo: raw.ESTNO ?? "",
        qty: raw.재고 ?? raw.qty ?? 0,
        bl: raw.BL ?? raw.bl ?? "",

        warehouse: raw.창고 ?? "",
        dueDate: raw.유통기한 ?? "",
        weight: raw.평중 ?? "",
        releaseDate: raw.출고일 ?? "",

        holding: raw.홀딩 ?? "",
        frozen: raw.동결 ?? "",
        unuse: raw.사용불가 ?? "",

        // 원본 보존 (디버깅용)
        raw
    };
}

/**
 * selectedItems Map에 안전하게 추가
 */
export function addSelectedItem(state, id, raw) {
    const item = normalizeItem(raw);
    if (!item) return;

    state.selectedItems.set(id, item);
}

/**
 * selectedItems 제거
 */
export function removeSelectedItem(state, id) {
    state.selectedItems.delete(id);
}

/**
 * 전체 초기화
 */
export function clearSelectedItems(state) {
    state.selectedItems.clear();
}

/**
 * 디버깅용 출력
 */
export function debugSelectedItems(state) {
    console.log("===== selectedItems =====");
    state.selectedItems.forEach((v, k) => {
        console.log(k, v);
    });
}