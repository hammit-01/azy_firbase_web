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
    reservationsSearch: "", // 예약 현황 탭 — 통합 검색어(전략단가와 동일 방식, 2026-08-20)
    reservationsWarehouseFilter: "", // 예약 현황 탭 — 창고 필터
    reservationsBrandFilter: "", // 예약 현황 탭 — 브랜드 필터
    reservationsSortColumns: [], // 예약 현황 탭 — 열 클릭 정렬([{key, dir}], 2026-08-25)
    salesDateFilter: "", // 타창고매출현황 탭 — 출고일 필터(YYYY-MM-DD, ""=오늘)
    salesSearch: "", // 타창고매출현황 탭 — 통합 검색어(전략단가와 동일 방식, 2026-08-20)
    salesWarehouseFilter: "", // 타창고매출현황 탭 — 창고 필터
    salesBrandFilter: "", // 타창고매출현황 탭 — 브랜드 필터
    salesManagerFilter: "", // 타창고매출현황 탭 — 담당자 필터(2026-08-25)
    // 타창고매출현황 탭 — 열 클릭 정렬([{key, dir}], 2026-08-25). 기본값을
    // 홀딩일자(예약/등록 시점) 내림차순으로 둬서 최신순이 기본이 되게 함
    // (2026-08-25) — 사용자가 다른 열을 클릭하면 그 선택으로 바뀜.
    salesSortColumns: [{ key: "홀딩일자", dir: 2 }],
    filteredReservations: [], // 예약/출고 현황 탭 — 툴바 검색·필터 적용된 현재 표시 행(엑셀 다운로드용)
    movesSearch: "", // 창고이동 탭 — 통합 검색어(2026-09-04, 관리자+8001 테스트 기능)
    movesDateFilter: "", // 창고이동 탭 — 등록일 필터(YYYY-MM-DD, ""=전체, 2026-09-04)
    filteredMoves: [], // 창고이동 탭 — 검색·날짜 필터 적용된 현재 표시 행(엑셀 다운로드용)
    priceSearch: "", // 전략단가 탭 — 통합 검색어
    priceCategoryFilter: "", // 전략단가 탭 — 분류 필터
    priceBrandFilter: "", // 전략단가 탭 — 브랜드 필터
    filteredPrices: [], // 전략단가 탭 — 검색·필터 적용된 현재 표시 행(엑셀 다운로드용)
    changesSearch: "", // 업데이트 탭 — 통합 검색어(전략단가와 동일 방식, 2026-08-20)
    changesWarehouseFilter: "", // 업데이트 탭 — 창고 필터
    changesBrandFilter: "", // 업데이트 탭 — 브랜드 필터
    orderSheetSearch: "", // 발주장 탭 — 통합 검색어(2026-08-26)
    orderSheetWarehouseFilter: "", // 발주장 탭 — 창고 필터
    orderSheetBrandFilter: "", // 발주장 탭 — 브랜드 필터
    orderSheetManagerFilter: "", // 발주장 탭 — 담당자 필터
};
