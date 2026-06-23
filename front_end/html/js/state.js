// 전역 상태(allData, selectedItems)

export const state = {
    allData: [],
    filteredData: [], // 현재 필터/검색 후 표시 중인 행
    selectedItems: new Map(),
    flashIds: new Set(),
    crudData: null,
    useDefaultOrder: true
};