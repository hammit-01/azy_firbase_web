// 전역 상태(allData, selectedItems)

export const state = {
    allData: [],
    filteredData: [],
    employees: [],      // 사원 목록
    selectedItems: new Map(),
    flashIds: new Set(),
    crudData: null,
    useDefaultOrder: true
};