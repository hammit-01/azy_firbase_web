azy_firebase read me

전체 데이터 흐름
크롤링 -> data.xlsx 업로드 -> firestore post -> get/post(update/delete/select)
+ issue firestore 구독료 (지금은 무료 버전 사용, get post 하루 천건 넘어가면 막힐 때 있음)

file
back_end
- data
- - 웹사이트에 띄울 데이터
- main.py 메인 실행 프로그램, 사이트 정보 불러오기 -> 크롤링 -> eda -> data 폴더에 띄우는 전 과정
- crawling_list.py 크롤링 프로그램
- warehouse_list.py 창고 사이트 정보 가져오는 프로그램
- list_eda.py
- rename_column.py 열 이름 재지정
- replace_name.py 품목 이름 대체
- data_eda.py(), else_df_eda(), jns_dea(제니스용) 크롤링 데이터 eda 후 data 폴더에 띄우는 프로그램
--> 최종 결과물 통합물류 사이트 2n개 사이트 크롤링 데이터
(ch, jns, plz/아직 eda 미완성) + (kd,ki,sjn,dch,hlk,hld) = 최종 data
+ issue: cs냉장 사이트 실종, data_eda.py 빈 프로그램

front_end: html, css, web event, firebase 연동(back_end로 이동 검토 중)
-> 미지의 늪 그 잡채
내가 코딩했지만 이게 무슨 구조?
데이터 흐름 거의 백그라운드 수준, 안보임
+ js를 배운 적이 없지만 일단 js로 전반적인 이벤트 작업 중
- main.js 웹 시작점
- state.js 전역 상태(data 저장 구조)
- dom.js DOM 요소 모음
+ 나는 DOM이 뭔지 모름

- firebase.js firebse 초기화
- firestoreService.js DB CRUD

- table.js table rendering
- panel.js panel rendering
- evnets.js event 처리

- data_eda.js 웹 사이트 내 사용 데이터 정규화
- holding.js 홀딩 로직
- selection.js 선택 상태 관리

+ front_end 프로그램 흐름
웹 실행 -> bindEvents() -> firestroe 실시간 구독 -> 데이터 들어오면 state 저장 -> renderTable(), renderPanel()
+ data 흐름
--> 렌더링 때는 item의 표시값 사용, 백엔드 때는 item.id 사용
state.allDate 읽음 -> 검색 filter -> 정렬 sort -> HTML 테이블 생성
+ 체크박스 evnet 흐름
체크박스 클릭 -> state.allData에서 item 찾기 -> addSelectedItem() -> state.selectedItems 저장 -> renderAll()
+ data eda: UI에서 쓰기 쉽게 변환
+ 패널출력
selectedItems 읽음 -> 선택 상품 목록 출력 -> 개수/날짜/비고 + 입력창 생성
+홀딩 버튼 클릭
holding btn 클릭 -> handleClick(e) -> 입력값 읽기 -> holdingData(item, qty, date, note)

++ firestoreService.js에 subsribeData(), insertItem(), updateItem(), deleteItem() 등 firestore와 직접 통신하는 함수 추가 예정

.gitignore github upload 시 무시 항목 기재
post.py Google firebase firestore data post
+ get.py 추가 예정

README.md