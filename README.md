# 창고 재고 관리 시스템

냉동·냉장 물류 창고의 재고 데이터를 자동 수집하고 웹에서 조회·편집하는 사내 재고 관리 툴.

---

## 전체 구조

```
크롤링 (Python) → EDA/정제 (pandas) → Firestore 업로드 (post.py) → 웹 UI (HTML/JS)
```

---

## 실행 방법

### 백엔드 — 크롤링 + 업로드

```bash
# 크롤링 + EDA 실행 (결과: jns.xlsx)
python main.py

# Firestore 업로드 포함 실행
# main.py 마지막 줄 post(jns) 주석 해제 후 실행
python main.py
```

> Firebase Admin SDK 키 파일(`azy7503-d80d9-firebase-adminsdk-*.json`)이 루트에 있어야 합니다. `.gitignore` 처리됨.

### 프론트엔드 — 로컬 서버

```bash
python -m http.server 8000
# http://localhost:8000/front_end/html/warehouse_main.html
```

> ES 모듈 import를 사용하므로 로컬 HTTP 서버 필수 (파일 직접 열기 불가).

### 배포 (Firebase Hosting)

```bash
firebase deploy --only hosting
```

> 배포 전 HTML 경로를 `./css/` → `/css/`로 변경해야 함. Bash `sed` 사용 권장 (PowerShell Get-Content/Set-Content는 한국어 인코딩 깨짐).

---

## 파일 구조

```
azy_firbase_web/
├── main.py                  # 파이프라인 진입점 (크롤링 → EDA → 업로드)
├── post.py                  # Firestore 업로더
├── back_end/
│   ├── crawling_list.py     # 창고 사이트 HTTP 크롤링
│   ├── crawling_handmade.py # 표준 패턴 외 사이트 크롤링
│   ├── back_eda_main.py     # EDA 파이프라인 오케스트레이터
│   ├── eda_ch_plz_cs.py     # CH·PLZ·CS 창고 EDA
│   ├── eda_else_df.py       # 기타 창고 EDA
│   ├── jns_eda.py           # 제니스(JNS) EDA
│   ├── eda_standard.py      # 공통 EDA 유틸
│   ├── eda_common.py
│   ├── eda_added.py
│   ├── eda_column.py
│   ├── replace_name.py      # 상품명 정규화
│   ├── equal_df.py          # 신규/삭제/수량변경 행 비교
│   ├── exception_safe.py    # EDA 안전 래퍼
│   └── data/                # 출력 엑셀 파일
└── front_end/html/
    ├── warehouse_main.html  # 진입점 (SPA)
    ├── warehouse_main.js    # JS 모듈 로더
    ├── css/
    │   └── warehouse_main.css
    └── js/
        ├── state.js         # 전역 상태 (allData, selectedItems 등)
        ├── firebase.js      # Firebase 초기화 + 5분 폴링
        ├── firestoreService.js  # Firestore CRUD
        ├── table.js         # 테이블 렌더링 + 정렬/검색
        ├── panel.js         # 사이드 패널 렌더링 (추가/수정/홀딩 카드)
        ├── events.js        # DOM 이벤트 바인딩
        ├── crud.js          # 비즈니스 로직 (holdingData, insertData 등)
        ├── crud_history.js  # Undo 스택
        ├── data_eda.js      # Firestore 원본 → UI 정규화
        ├── dom.js           # DOM 요소 캐시
        ├── input_calculater.js  # 홀딩 수량 합계 계산
        └── actions.js       # 패널 모드 상수
```

---

## Firebase 설정

| 항목 | 값 |
|---|---|
| 프로젝트 ID | `azy7503-d80d9` |
| Firestore 컬렉션 | `all_data`, `holding_data`, `employees` |
| Firestore 규칙 | `allow read, write: if true` (인증 없음) |
| Hosting URL | https://azy7503-d80d9.web.app |
| Secondary DB | `awhw-0001` (장애 대비 이중화, `_meta/active_db` 마커로 자동 전환) |

---

## Firestore 문서 스키마 (`all_data`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `상품명` | string | |
| `브랜드` | string | |
| `등급` | string | |
| `ESTNO` | string | |
| `재고` | int | 박스 수 |
| `BL` | string | BL 번호 |
| `창고` | string | |
| `유통기한` | string | YYYY-MM-DD |
| `평중` | float | 평균 중량(kg) |
| `출고일` | string | |
| `홀딩` | string | 담당자명 |
| `상태` | string | `""` / `holding` / `freeze` / `stopped` / `moving` |
| `메모` | string | |
| `pk` | string | `{BL_last4}_{expire_date}_{weight}` 복합키 |
| `holdingRecordId` | string | holding_data 연결 ID (홀딩 행만) |

---

## 프론트엔드 동작 흐름

```
페이지 로드
  → bindEvents()
  → initFirebase() → subscribeData()
      → fetchAllData() (최초 1회 + 5분 간격 폴링)
          → state.allData 갱신
          → renderTable() + renderSelectData()

체크박스 클릭
  → addSelectedItem() → state.selectedItems 갱신
  → 해당 행 클래스 토글 (테이블 재렌더 없음)
  → 패널 업데이트 (renderSelectData / renderUpdate / renderHolding)

추가·수정·홀딩 버튼
  → 같은 버튼 재클릭 시 패널 닫힘 (토글)
  → crud.js → firestoreService.js → Firestore write
  → 5분 후 폴링으로 갱신 반영
```

---

## 주요 제약 사항

- Firestore 무료 티어: 읽기/쓰기 하루 ~1,000건 (현재 5분 폴링으로 절감)
- `back_eda_main.py`에 `sys.path` 하드코딩 있음 — 다른 PC에서 실행 시 수정 필요
- Firebase Admin SDK 키 파일은 `.gitignore` 처리 — 배포 환경에 별도 보관
