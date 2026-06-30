# 창고 재고 관리 시스템

냉동·냉장 물류 창고의 재고 데이터를 자동 수집하고 웹에서 조회·편집하는 사내 재고 관리 툴.

---

## 목차

1. [전체 아키텍처](#1-전체-아키텍처)
2. [디렉토리 구조](#2-디렉토리-구조)
3. [환경 요구사항](#3-환경-요구사항)
4. [초기 설정](#4-초기-설정)
5. [서비스 실행](#5-서비스-실행)
6. [파이프라인 상세](#6-파이프라인-상세)
7. [Firebase 이중화 구조](#7-firebase-이중화-구조)
8. [Firestore 스키마](#8-firestore-스키마)
9. [홀딩 시스템](#9-홀딩-시스템)
10. [웹 UI 구조](#10-웹-ui-구조)
11. [백엔드 EDA](#11-백엔드-eda)
12. [배포 (Firebase Hosting)](#12-배포-firebase-hosting)
13. [트러블슈팅](#13-트러블슈팅)

---

## 1. 전체 아키텍처

```
[창고 사이트 HTTP]
       ↓  crawling_list.py / crawling_handmade.py
[원시 데이터 DataFrame]
       ↓  back_eda_main.py → eda_*.py → replace_name.py
[정제된 DataFrame (jns.xlsx)]
       ↓  pipeline/updater.py  (서비스 모드)
          post.py              (수동 모드)
[Firestore all_data 컬렉션]
       ↓  firebase.js (5분 폴링)
[웹 UI — warehouse_main.html]
```

### 핵심 설계 원칙

| 원칙 | 구현 |
|---|---|
| 중복 없는 doc 식별 | `doc_id = BL_유통기한_상품명` 복합키 (창고 코드 무관) |
| 홀딩 수량 보정 | 업로드 전 홀딩 합계 차감 → 원본 재고 = 크롤링 - 홀딩 |
| 사용자 데이터 보존 | `상태·홀딩·메모` 필드는 크롤링이 덮어쓰지 않음 (`set merge=True`) |
| Firestore 할당량 관리 | Primary 초과 시 Secondary 자동 폴백, 23시간 후 자동 복귀 |
| 재고 변화 감지 | snapshot.pkl 로컬 스냅샷 비교 → 변경된 행만 Firestore 업데이트 |

---

## 2. 디렉토리 구조

```
azy_firbase_web/
│
├── run_service.py              # 파이프라인 서비스 진입점 (python run_service.py)
├── main.py                     # 수동 크롤링+EDA 진입점
├── post.py                     # 수동 Firestore 업로더 (main.py에서 호출)
│
├── pipeline/                   # 자동화 파이프라인 (서비스 모드)
│   ├── scheduler.py            # APScheduler: 평일 08:00~17:00 1분 간격 실행
│   ├── crawler.py              # 병렬 크롤링 + EDA 정규화 래퍼
│   ├── updater.py              # Firestore diff 업데이트 + Primary/Secondary 이중화
│   ├── snapshot.py             # snapshot.pkl 로드/저장 (변경 감지용)
│   ├── snapshot.pkl            # 마지막 업로드 상태 캐시 (자동 생성, gitignore)
│   ├── active_db.json          # 현재 활성 DB 상태 (자동 생성, gitignore)
│   └── logs/
│       ├── pipeline.log        # 파이프라인 실행 로그 (UTF-8)
│       ├── service_out.txt     # 서비스 표준 출력
│       └── service_err.txt     # 서비스 표준 에러
│
├── back_end/
│   ├── crawling_list.py        # HTTP 크롤링 (로그인 → 데이터 수집)
│   ├── crawling_handmade.py    # 비표준 사이트 수동 크롤링
│   ├── back_eda_main.py        # EDA 오케스트레이터 (list_eda 함수)
│   ├── jns_eda.py              # 제니스(곤지암) 전용 EDA
│   ├── eda_ch_plz_cs.py        # CH·PLZ·CS 창고 EDA
│   ├── eda_else_df.py          # 기타 창고 EDA
│   ├── eda_standard.py         # 공통 EDA 유틸리티
│   ├── eda_common.py           # 공통 전처리 함수
│   ├── eda_added.py            # 추가 정제 로직
│   ├── eda_column.py           # 컬럼 표준화
│   ├── replace_name.py         # 상품명 정규화 사전
│   ├── equal_df.py             # 기존 재고장과 신규 데이터 비교 (new/deleted/!)
│   ├── exception_safe.py       # EDA 함수 안전 래퍼
│   └── data/
│       ├── warehouse_list.xlsx # 창고 목록 및 로그인 정보
│       └── *.xlsx              # EDA 결과물 및 비교 기준 파일
│
├── front_end/html/
│   ├── warehouse_main.html     # SPA 진입점
│   ├── css/
│   │   └── warehouse_main.css
│   └── js/
│       ├── firebase.js         # Firebase 초기화, Primary/Secondary 전환, 5분 폴링
│       ├── firestoreService.js # Firestore CRUD (insertItem, updateItem, deleteItem)
│       ├── state.js            # 전역 상태 (allData, selectedItems, flashIds, crudData)
│       ├── table.js            # 테이블 렌더링 (정렬, 검색, 색상 구분, 모바일 뷰)
│       ├── panel.js            # 사이드 패널 (추가/수정/홀딩/선택 카드)
│       ├── events.js           # DOM 이벤트 바인딩 + 호버 카드
│       ├── crud.js             # 비즈니스 로직 (holdingData, insertData, updateData, deleteItem)
│       ├── crud_history.js     # Undo 스택 (undoStack, undoLastAction)
│       ├── data_eda.js         # Firestore 원본 → UI 정규화, addSelectedItem
│       ├── dom.js              # DOM 요소 캐시
│       ├── input_calculater.js # 홀딩 수량·중량 합계 계산
│       └── actions.js          # 패널 모드 enum 상수
│
├── scripts/                    # 유지보수용 일회성 스크립트
│   ├── switch_to_secondary.py  # Secondary 수동 전환
│   ├── switch_to_primary.py    # Primary 수동 복귀
│   ├── copy_holdings_to_secondary.py  # Primary → Secondary 홀딩 복사
│   ├── restore_holdings_from_txt.py   # txt 백업에서 홀딩 복원
│   ├── fix_duplicate_origin.py # 중복 원본행 수량 합산 정리
│   ├── migrate_doc_ids.py      # doc_id 포맷 마이그레이션
│   ├── diagnose.py             # Firestore 수량 진단
│   └── check_holding2.py       # 홀딩 수량 검증 리포트
│
├── .firebase/                  # Firebase Hosting 캐시 (gitignore 대상 아님)
├── firebase.json               # Firebase Hosting 설정
├── .firebaserc                 # 프로젝트 연결 설정
├── CLAUDE.md                   # AI 어시스턴트용 프로젝트 가이드
└── README.md                   # 이 파일
```

---

## 3. 환경 요구사항

| 항목 | 버전 / 비고 |
|---|---|
| Python | 3.10 이상 (3.14 사용 중) |
| 주요 패키지 | `firebase-admin`, `google-cloud-firestore`, `pandas`, `requests`, `apscheduler`, `openpyxl` |
| Firebase CLI | `firebase deploy` 배포 시 필요 |
| 브라우저 | ES 모듈 지원 브라우저 (Chrome, Edge 최신) |
| OS | Windows 10/11 (경로 일부 하드코딩 주의) |

```bash
pip install firebase-admin google-cloud-firestore pandas requests apscheduler openpyxl
```

---

## 4. 초기 설정

### 4-1. Firebase Admin SDK 키 파일

두 개의 Firebase 프로젝트에 대한 Admin SDK 서비스 계정 키가 필요합니다.

```
azy7503-d80d9-firebase-adminsdk-fbsvc-60e8882c5b.json  ← Primary
awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json       ← Secondary
```

발급 방법:
> Firebase 콘솔 → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성

두 파일 모두 **프로젝트 루트**에 위치해야 합니다. `.gitignore`에 등록되어 있으므로 git에 올라가지 않습니다.

### 4-2. Firestore 초기화

- Primary (`azy7503-d80d9`): 컬렉션 `all_data`, `employees`, `archive_data`
- Secondary (`awhw-0001`): 컬렉션 `all_data`, `_meta`
- Firestore 규칙: `allow read, write: if true` (인증 없음, 사내 전용)

### 4-3. 창고 목록 파일

`back_end/data/warehouse_list.xlsx` — 창고명, IP:Port, 로그인 ID/PW, 고객코드 등을 포함합니다.
현재 활성 창고: **제니스(곤지암)** (crawler.py 25번째 줄에서 필터링)

```python
# crawler.py
active = df[df["창고"] == "제니스(곤지암)"]  # 필요 시 다른 창고 추가
```

---

## 5. 서비스 실행

### 5-1. 파이프라인 서비스 (자동 크롤링)

```powershell
# 백그라운드 서비스로 실행
$pythonExe = "C:\Users\OWNER\AppData\Local\Python\pythoncore-3.14-64\python.exe"
Start-Process -FilePath $pythonExe -ArgumentList "run_service.py" `
    -WorkingDirectory "C:\Users\OWNER\.vscode\azy_firbase_web" `
    -WindowStyle Hidden
```

- 스케줄: **평일(월~금) 08:00 ~ 17:00, 1분 간격**
- 운영 시간 내 시작 시 즉시 1회 실행 후 스케줄 진입
- 로그: `pipeline/logs/pipeline.log` (UTF-8, 한국어 정상 기록)

```powershell
# 프로세스 확인
Get-WmiObject Win32_Process | Where-Object { $_.Name -like "python*" }

# 프로세스 종료
Get-Process python* | Stop-Process -Force
```

### 5-2. 웹 서버 (로컬 개발)

```bash
python -m http.server 8000
# 접속: http://localhost:8000/front_end/html/warehouse_main.html
```

ES 모듈(`import`/`export`) 사용으로 반드시 HTTP 서버 통해야 합니다. 파일 직접 열기(`file://`)는 동작 안 합니다.

### 5-3. 수동 크롤링 + 업로드

```bash
# 크롤링 + EDA만 실행 (Firestore 업로드 안 함)
python main.py

# Firestore 업로드 포함 (main.py에서 post(jns) 주석 해제 후)
python main.py
```

---

## 6. 파이프라인 상세

### 6-1. 실행 흐름

```
scheduler.py::run_pipeline()
    ↓
CrawlerPool.crawl_all()          # 병렬 HTTP 크롤링
    ↓
CrawlerPool.normalize(results)   # back_eda_main.list_eda() 호출
    ↓
Snapshot.load()                  # snapshot.pkl → 이전 상태 dict 로드
    ↓
FirestoreUpdater.update_diff()   # 변경 감지 + Firestore 업데이트
    ↓
Snapshot.save(new_snap)          # 새 상태 저장
```

### 6-2. `updater.py` — Firestore diff 업데이트

`update_diff(new_df, prev_snapshot)` 내부 동작:

```
1. 활성 DB 결정 (active_db.json 기준: primary or secondary)
2. Firestore에서 홀딩 행 조회 → holding_sum {(BL, 상품명, 유통기한): 수량}
3. _df_to_dict(new_df, today, holding_sum)
   - 각 행의 doc_id 생성: f"{BL}_{유통기한}_{상품명}" (특수문자 → _)
   - 재고 = 크롤링수량 - 홀딩수량 (순수 잔여 수량)
   - 순재고 ≤ 0이면 해당 행 스킵 (전량 홀딩)
   - 동일 doc_id 충돌 시 재고 합산 (창고 코드 다른 같은 상품)
4. 이전 스냅샷과 비교:
   - to_insert: 스냅샷에 없는 신규 doc → set() + 사용자 필드 초기화
   - to_update: 시그니처(주요 필드 해시) 변경된 doc → set(merge=True)
   - to_delete: 스냅샷에 있으나 신규 데이터에 없는 doc → delete()
5. Firestore 배치 처리 (250건 단위)
6. 할당량 초과 시 → _fallback_to_secondary() 자동 호출
```

**비교 대상 필드 (`COMPARE_FIELDS`):**
```python
("상품명", "브랜드", "등급", "ESTNO", "재고", "BL", "창고", "유통기한", "평중", "출고일")
```
`상태·홀딩·메모`는 사용자 설정 필드이므로 비교 및 덮어쓰기 대상 제외.

### 6-3. `snapshot.pkl`

- Python `pickle` 형식으로 `pipeline/snapshot.pkl`에 저장
- 내용: `{doc_id: {필드: 값, ...}}` 딕셔너리
- 파이프라인 재시작 시 자동 복구. 없으면 전체 쓰기로 진행
- **초기화가 필요한 경우:** 파일 삭제 후 서비스 재시작

### 6-4. doc_id 체계

```
doc_id = "{BL번호}_{유통기한YYYYMMDD}_{상품명}"
         (/, 공백 → _로 치환)

예시: MAEU269042936_20280413_삼겹
```

- 창고 코드와 무관하게 동일 상품이면 동일 doc_id 보장
- `post.py`, `updater.py`, `migrate_doc_ids.py` 모두 동일 포맷 사용
- 과거에 사용하던 `코드_BL_유통기한` 포맷은 폐기됨

---

## 7. Firebase 이중화 구조

### 7-1. 구성

| 구분 | 프로젝트 ID | 용도 |
|---|---|---|
| Primary | `azy7503-d80d9` | 메인 운영 DB |
| Secondary | `awhw-0001` | 할당량 초과 시 자동 폴백 |

### 7-2. 자동 전환 흐름 (Backend)

```
파이프라인 Firestore 쓰기 실패 (429 Quota exceeded)
    ↓
_fallback_to_secondary() 호출
    ↓
_activate_secondary()
  - pipeline/active_db.json 저장: {"active": "secondary", "switched_at": "..."}
  - Secondary Firestore: _meta/active_db 문서 저장 {"active": "secondary"}
    ↓
현재 크롤링 데이터 전체를 Secondary에 기록 (set merge=True)
    ↓
다음 파이프라인 실행부터 Secondary 사용
    ↓
23시간 경과 후 → _try_recover_primary()
  - Primary에 데이터 쓰기 시도
  - 성공 시 → _activate_primary() → active_db.json 삭제 + _meta/active_db 마커 삭제
  - 실패 시 → Secondary 유지 (다음 라운드 재시도)
```

### 7-3. 자동 전환 흐름 (Frontend)

```javascript
// firebase.js
onSnapshot(doc(_secondaryDb, "_meta", "active_db"), (snap) => {
    const newActive = snap.exists() ? snap.data().active : "primary";
    if (newActive !== _activeDbName) {
        setTimeout(() => window.location.reload(), 800); // 감지 시 자동 리로드
    }
});
```

- 프론트엔드는 Secondary의 `_meta/active_db` 문서를 **실시간 감시**
- 백엔드가 마커를 쓰면 800ms 후 페이지 자동 리로드 → 새 DB 사용
- 마커 삭제(Primary 복귀) 시에도 동일하게 감지

### 7-4. 수동 전환 스크립트

```bash
# Secondary로 수동 전환 (Primary 할당량 초과 시)
python scripts/switch_to_secondary.py

# Primary로 수동 복귀
python scripts/switch_to_primary.py

# Primary → Secondary 홀딩 데이터 복사 (Primary 접근 가능한 경우)
python scripts/copy_holdings_to_secondary.py

# 저장된 txt 파일에서 홀딩 복원 (Primary 접근 불가 시)
python scripts/restore_holdings_from_txt.py
```

### 7-5. Firestore 무료 티어 할당량

| 항목 | 무료 한도 |
|---|---|
| 문서 읽기 | 50,000건/일 |
| 문서 쓰기 | 20,000건/일 |
| 문서 삭제 | 20,000건/일 |

**할당량 리셋 시각:** 매일 **오전 00:00 PDT (한국 기준 16:00~17:00)**

운영 시간(08:00~17:00) 1분 간격 = 하루 최대 540번 파이프라인 실행.
Firestore는 변경된 행만 업데이트하므로 실제 쓰기는 훨씬 적습니다.
진단/마이그레이션 스크립트는 전체 컬렉션 읽기(stream)를 사용하므로 할당량 소모가 큼 — 필요할 때만 실행할 것.

---

## 8. Firestore 스키마

### 8-1. `all_data` 컬렉션

모든 재고 행과 홀딩 행이 이 컬렉션에 공존합니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | Firestore 문서 ID (doc_id와 동일, 홀딩은 UUID) |
| `pk` | string | `id`와 동일값 (레거시 호환용) |
| `상품명` | string | 수탁품명 |
| `브랜드` | string | 브랜드명 |
| `등급` | string | 품질 등급 |
| `ESTNO` | string | EST 인증 번호 |
| `재고` | int | 박스 수 (홀딩 차감 후 잔여 수량 또는 홀딩 수량) |
| `BL` | string | BL 번호 전체 (예: `MAEU269042936`) |
| `창고` | string | 창고명 |
| `유통기한` | string | `YYYY-MM-DD` 형식 |
| `중량` | float | 개당 중량(kg) |
| `평중` | float | 평균 중량(kg) |
| `출고일` | string | 출고 예정일 (`YYYY-MM-DD`) |
| `홀딩` | string | 홀딩 담당자명 (홀딩 행) 또는 비고 (원본 행) |
| `수집일` | string | 크롤링 날짜 `YYYY-MM-DD` (홀딩 행은 빈 문자열) |
| `상태` | string | `"없음"` (일반), `"holding"` (홀딩), `"freeze"`, `"stopped"`, `"moving"` |
| `메모` | string | 사용자 입력 메모 |

**원본 행 vs 홀딩 행 구분:**

| 구분 | `상태` | `수집일` | `id` 형식 |
|---|---|---|---|
| 원본 행 | `"없음"` | `YYYY-MM-DD` | `BL_유통기한_상품명` |
| 홀딩 행 | `"holding"` | `""` | UUID (auto-generated) |

### 8-2. `employees` 컬렉션

사용자 목록. 홀딩·삽입 시 담당자 선택에 사용.

| 필드 | 타입 |
|---|---|
| `이름` | string |
| `역할` | string |

### 8-3. `archive_data` 컬렉션

이전 수집일의 데이터를 보관합니다. `post.py`의 `_archive_old_data()` 함수가 `수집일 != 오늘`인 원본 행을 이동시킵니다. (파이프라인 서비스는 snapshot 비교 방식이라 별도 아카이브 없음)

### 8-4. `_meta` 컬렉션 (Secondary만)

| 문서 ID | 필드 | 설명 |
|---|---|---|
| `active_db` | `active: "secondary"` | Primary → Secondary 전환 시 생성 |
| `active_db` | `switched_at: ISO8601` | 전환 시각 |

Primary 복귀 시 이 문서가 삭제됩니다.

---

## 9. 홀딩 시스템

### 9-1. 개념

홀딩(Holding)은 재고를 출고 예약 상태로 분리하는 기능입니다.

```
[원본 재고 100박스]
       ↓ 홀딩 60박스 (holdingData)
[원본 행: 재고 40박스] + [홀딩 행: 재고 60박스, 상태=holding]
```

- `holdingData(item, holdQty, ...)` — 원본 행 재고를 `holdQty`만큼 줄이고, 홀딩 행(UUID ID)을 새로 생성
- 홀딩 행은 `상태: "holding"`, `수집일: ""` — 파이프라인이 건드리지 않음
- 원본 행은 `재고 -= holdQty`로 감소

### 9-2. 크롤링과 홀딩의 관계

파이프라인(updater.py)은 크롤링 업로드 전 홀딩 수량을 차감합니다:

```python
holding_sum = {(BL, 상품명, 유통기한): 홀딩수량합계}  # Firestore 홀딩 행 집계
net_qty = crawled_qty - holding_sum.get((bl, name, expire), 0)
# net_qty <= 0 이면 원본 doc 업로드 스킵 (전량 홀딩 중)
```

이렇게 하면 매 크롤링마다 홀딩이 초기화되지 않고, 원본 행의 재고가 항상 실제 잔여분을 반영합니다.

### 9-3. 완료 처리

웹 UI의 `사용` 열 ✓ 버튼 클릭 → 홀딩 행 삭제 → 원본 행 없음 (전량 홀딩이었으면 다음 크롤링에서 원본 행 재생성)

### 9-4. 홀딩 수량 검증

```bash
python scripts/check_holding2.py
# 결과: scripts/holding_check_result.txt
```

출력 형식:
```
BL              상품명   유통기한   원본  홀딩합  합계  홀딩 상세
MAEU269042936   삼겹  2028-04-13  430   300   730  미상:200박스(출고 2026-07-03)  미상:100박스(출고 미정)
```

---

## 10. 웹 UI 구조

### 10-1. JS 모듈 의존관계

```
warehouse_main.html
  └── warehouse_main.js (type="module")
        ├── firebase.js    → state.js, table.js, panel.js
        ├── events.js      → dom.js, state.js, crud.js, data_eda.js, actions.js
        ├── table.js       → state.js, dom.js
        ├── panel.js       → state.js, dom.js, actions.js
        ├── crud.js        → firestoreService.js, state.js, crud_history.js
        └── data_eda.js    → state.js, panel.js, table.js
```

### 10-2. 렌더링 흐름

```
[페이지 로드]
  bindEvents()         ← events.js: 모든 DOM 이벤트 등록
  initFirebase()       ← firebase.js: Primary/Secondary 결정 + 5분 폴링 시작
  subscribeData()
    → fetchAllData()
        → getDocs(all_data)
        → state.allData = [...]
        → renderTable()      ← table.js: tbody 전체 재렌더
        → renderSelectData() ← panel.js: 선택 항목 패널 업데이트

[행 더블클릭]
  addSelectedItem()    ← data_eda.js: 행 정규화 후 state.selectedItems에 추가
  renderAll()          ← table.js + panel.js

[홀딩 버튼]
  holdingData()        ← crud.js: 원본 재고 감소 + 홀딩 행 생성
    → updateItem()     ← firestoreService.js
    → insertItem()     ← firestoreService.js
  undoStack에 push     ← crud_history.js
  5분 후 다음 폴링에서 갱신 반영
```

### 10-3. 테이블 컬럼 구성

| 순서 | 컬럼 | 너비 | 비고 |
|---|---|---|---|
| 1 | 선택 (체크박스) | 3% | |
| 2 | 상품명 | 12% | |
| 3 | 브랜드 | 12% | |
| 4 | 등급 | 7% | |
| 5 | ESTNO | 8% | |
| 6 | 재고 | 7% | |
| 7 | BL | 16% | |
| 8 | 창고 | 10% | |
| 9 | 유통기한 | 8% | |
| 10 | 평균중량 | 5% | |
| 11 | 메모 | 10% | |
| 12 | 사용 (완료 버튼) | 3% | 홀딩 행만 표시 |

출고일·홀딩 정보는 테이블에서 제거하고, 행에 마우스 올리면 호버 카드로 표시됩니다.

### 10-4. 행 색상 구분

| 상태 | 색상 |
|---|---|
| 일반 (`없음`) | 기본 (검정) |
| 홀딩 (`holding`) | 파랑 `#007de4` |
| 선택됨 | 초록 `#2e9100` |
| 동결 (`freeze`) | 보라 `#6d28d9` |
| 중단 (`stopped`) | 갈색 `#92400e` |
| 이동 (`moving`) | 주황 `#ff8838` |

### 10-5. Firebase 초기화 (Primary/Secondary 결정)

```javascript
// firebase.js 초기화 순서
initFirebase()
  1. Primary, Secondary 앱 초기화
  2. Secondary의 _meta/active_db 문서 조회 (일회성)
     - 존재하고 active==="secondary" → _activeDbName = "secondary"
  3. _meta/active_db 실시간 감시 (onSnapshot)
     - 변경 감지 시 800ms 후 window.location.reload()
  4. db = _activeDbName==="secondary" ? _secondaryDb : _primaryDb
```

---

## 11. 백엔드 EDA

### 11-1. 파이프라인 흐름

```
crawling_list.py::get_data()       # 사이트별 원시 데이터 수집
       ↓
back_eda_main.py::list_eda()       # 오케스트레이터
       ↓
jns_eda.py / eda_ch_plz_cs.py / eda_else_df.py  # 창고별 전처리
       ↓
eda_standard.py / eda_common.py / eda_added.py  # 공통 정제
       ↓
replace_name.py                    # 상품명 표준화 사전 적용
       ↓
eda_column.py                      # 출력 컬럼 표준화
       ↓
정제된 DataFrame (컬럼: BL번호, 수탁품, 유통기한, 재고수량, 브랜드, 등급, ESTNO, 창고, 중량, 평균중량, 출고예정일, 코드, ...)
```

### 11-2. pk 기반 중복 합산

EDA 내부에서 동일 pk(창고코드+BL+유통기한) 기준으로 1차 합산이 이루어집니다.
파이프라인의 `_df_to_dict()`에서 동일 doc_id(BL+유통기한+상품명) 기준으로 2차 합산합니다.
이중 합산으로 창고 코드가 달라도 같은 상품이면 단일 Firestore 문서로 병합됩니다.

### 11-3. `equal_df.py` — 재고 변화 비교

기존 재고장(`[창고]재고장(전미림).xlsx`)과 새 크롤링 데이터를 비교해 행에 상태를 붙입니다:
- `new`: 새로 들어온 재고
- `deleted`: 사라진 재고
- `!`: 수량 변경됨

이 파일은 웹 UI에 직접 연동되지 않고, 재고 변화 확인용 보고서 생성에 사용됩니다.

---

## 12. 배포 (Firebase Hosting)

### 12-1. 경로 변경

로컬 서버(`./css/...`)와 Firebase Hosting(`/css/...`) 경로가 다릅니다.
배포 전 Bash `sed`로 변환합니다 (PowerShell은 한국어 인코딩 깨짐).

```bash
# 로컬 → 배포 (배포 전)
sed -i 's|\./css/|/css/|g; s|\./js/|/js/|g' front_end/html/warehouse_main.html

# 배포
firebase deploy --only hosting

# 배포 후 로컬로 복구
sed -i 's|"/css/|"./css/|g; s|"/js/|"./js/|g' front_end/html/warehouse_main.html
```

> **주의:** `Get-Content | Set-Content` (PowerShell)는 한국어 문자를 UTF-16으로 재인코딩해 깨집니다.

### 12-2. 배포 URL

```
https://azy7503-d80d9.web.app
https://azy7503-d80d9.firebaseapp.com
```

---

## 13. 트러블슈팅

### Firestore 할당량 초과 (`429 Quota exceeded`)

**증상:** 웹 UI에 데이터 안 보임, 파이프라인 로그에 할당량 초과

**자동 처리:** 파이프라인이 Secondary로 자동 전환 + 프론트엔드 자동 리로드

**수동 처리:**
```bash
python scripts/switch_to_secondary.py   # Secondary 전환
# 서비스 재시작 (PID 확인 후 Kill → 재시작)
```

**할당량 리셋:** 매일 한국 기준 오후 4~5시 (PDT 00:00)

---

### 데이터 수량 불일치

**원인 1:** snapshot.pkl에 구버전 doc_id가 남아있어 중복 doc 생성

```bash
# snapshot.pkl 삭제 후 서비스 재시작 → 전체 재쓰기
del pipeline\snapshot.pkl
```

**원인 2:** 홀딩 데이터와 원본 데이터 이중계산

```bash
python scripts/check_holding2.py        # 홀딩 수량 검증
python scripts/diagnose.py              # 중복 원본행 탐지
python scripts/fix_duplicate_origin.py  # 중복 원본행 합산 정리
```

---

### 파이프라인 서비스가 시작 안 됨 (cp949 인코딩 오류)

**증상:** `UnicodeEncodeError: 'cp949' codec can't encode character`

**원인:** `py run_service.py 2>&1` 처럼 stderr를 PowerShell에 리다이렉트하면 한국어·유니코드가 cp949로 강제 인코딩됨

**해결:**
```powershell
# 올바른 실행 방법 (WindowStyle Hidden → 터미널 없이 실행)
Start-Process -FilePath "python" -ArgumentList "run_service.py" `
    -WorkingDirectory "프로젝트경로" -WindowStyle Hidden
```

---

### PowerShell에서 한국어 파일 인코딩 깨짐

**원인:** `Get-Content | Set-Content` 기본 인코딩이 UTF-16

**해결:** 파일 내용 치환은 반드시 Bash `sed` 사용
```bash
sed -i 's/찾을텍스트/바꿀텍스트/g' 파일명
```

---

### `back_eda_main.py` 경로 오류

`sys.path.append('C:\\Users\\ASUS\\...')` 하드코딩이 있습니다.
다른 PC에서 실행 시 이 경로를 수정하거나 주석 처리하세요.

---

### 홀딩 데이터 Secondary 복원

Primary 접근 가능한 경우:
```bash
python scripts/copy_holdings_to_secondary.py
```

Primary 할당량 초과로 접근 불가한 경우:
```bash
# scripts/holding_check_result.txt (마지막 check_holding2.py 결과)에서 복원
python scripts/restore_holdings_from_txt.py
```

---

## 개발 메모

- **Firebase SDK 버전:** CDN `12.12.0` (npm 설치 없음)
- **Firestore Python SDK:** `FieldFilter` 클래스 필수 (`where(filter=FieldFilter(...))`)  
  구버전 `.where("field", "==", value)` 문법은 한국어 필드명에서 오류 발생
- **홀딩 행 보존:** `_archive_old_data()` 및 `update_diff()`는 `수집일`이 없는(빈 문자열) 홀딩 행을 건드리지 않음
- **모바일 뷰:** `table.js::renderMobileView()` — 768px 이하에서 카드형 레이아웃, `limitDate` 변수는 함수 내부에서 별도 선언 필요
