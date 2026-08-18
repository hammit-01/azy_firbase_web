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
    reservationsFilter: "", // 예약 현황 탭 — 담당자 필터(편집자 전용, ""=전체)
    reservationsDateFilter: "", // 예약 현황 탭 — 출고일 필터(YYYY-MM-DD, ""=전체)
    salesDateFilter: "", // 타창고매출현황 탭 — 출고일 필터(YYYY-MM-DD, ""=오늘)
    filteredReservations: [], // 예약/출고 현황 탭 — 툴바 검색·필터 적용된 현재 표시 행(엑셀 다운로드용)
};
