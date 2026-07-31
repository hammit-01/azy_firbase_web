// 전역 상태(allData, selectedItems)

export const state = {
    allData: [],
    yesterdayById: new Map(), // 업데이트 탭 비교 기준 — 어제 마감 스냅샷(id → row)
    filteredData: [],
    employees: [],      // 사원 목록
    selectedItems: new Map(),
    flashIds: new Set(),
    crudData: null,
    useDefaultOrder: true,
    sortColumns: [],    // [{key, dir}] dir: 1=오름차, 2=내림차
};