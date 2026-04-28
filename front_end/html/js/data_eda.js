// data_eda.js
// Firebase raw data -> UI friendly normalized data layer

/**
 * raw Firebase 데이터를 UI에서 쓰기 좋게 변환 (EDA: Extract, Deduplicate, Adapt)
 */
export function normalizeItem(raw) {
    if (!raw) return null;

    return {
        id: raw.id ?? raw._id ?? null,

        name: raw.상품명 ?? raw.name ?? raw.itemName ?? null,
        brand: raw.브랜드 ?? null,
        grade: raw.등급 ?? null,
        estNo: raw.ESTNO ?? null,
        qty: raw.재고 ?? raw.qty ?? 0,
        bl: raw.BL ?? raw.bl ?? null,

        warehouse: raw.창고 ?? null,
        dueDate: raw.유통기한 ?? null,
        weight: raw.평중 ?? null,
        releaseDate: raw.출고일 ?? null,

        holding: raw.홀딩 ?? null,
        frozen: raw.동결 ?? null,
        unuse: raw.사용불가 ?? null,

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