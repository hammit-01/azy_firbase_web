// 전역 상태(allData, selectedItems)

export const state = {
    allData: [],
    filteredData: [],
    employees: [],      // 사원 목록
    selectedItems: new Map(),
    flashIds: new Set(),
    crudData: null,
    useDefaultOrder: true,
    sortColumn: null,   // 정렬 중인 열 key (null = 없음)
    sortDir: 0          // 0: 없음, 1: 내림차, 2: 오름차
};