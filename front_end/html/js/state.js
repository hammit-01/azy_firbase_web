// 전역 상태(allData, selectedItems)

export const state = {
    allData: [], // 전체 재고 데이터
    selectedItems: new Map(), // 체크한 상품들
    flashIds: new Set(), // 홀딩된 행 일시 표시
    crudData: null, // crud 섹션 표시
    // dataState: [0,1,2,3], // 상태 표시 차례대로 홀딩, 동결, 사용불가, 이고

    useDefaultOrder: true
};