// 전역 상태(allData, selectedItems)

export const state = {
    allData: [],
    filteredData: [],
    employees: [],      // 사원 목록
    selectedItems: new Map(),
    flashIds: new Set(),
    crudData: null,
    useDefaultOrder: true,
    sortColumns: [],    // [{key, dir}] dir: 1=오름차, 2=내림차
    pendingChanges: [], // 재고 감소 미확인 항목
};