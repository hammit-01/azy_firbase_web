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
7. [MySQL 스키마](#7-mysql-스키마)
8. [홀딩 시스템](#8-홀딩-시스템)
9. [출고 자동 차감 (Google Sheets)](#9-출고-자동-차감-google-sheets)
10. [웹 UI 구조](#10-웹-ui-구조)
11. [API 서버](#11-api-서버)
12. [트러블슈팅](#12-트러블슈팅)

---

## 1. 전체 아키텍처

```
[창고 사이트 HTTP]
       ↓  back_end/crawling_list.py
[원시 DataFrame]
       ↓  back_end/back_eda_main.py → eda_*.py → replace_name.py
[정제된 DataFrame]
       ↓  pipeline/updater.py  (snapshot.pkl 기반 변경 감지)
[MySQL DB — azy_warehouse]
       ↓  api_server.py  (FastAPI, port 8000)
[웹 UI — warehouse_main.html]
```

### 핵심 설계 원칙

| 원칙 | 구현 |
|---|---|
| 중복 없는 행 식별 | `pk = 코드_BL뒤4자리_식별번호뒤4자리_유통기한YYYYMMDD` |
| 홀딩 수량 보정 | 크롤 수량 - holding_records 합계 = 실제 표시 재고 |
| 크롤 vs 홀딩 분리 | 크롤 행: `수집일=날짜`, 홀딩 행: `수집일=''` → 파이프라인이 홀딩 행 건드리지 않음 |
| 재고 변화 감지 | `snapshot.pkl` 이전 상태 비교 → 변경된 행만 MySQL 업데이트 |
| 출고 자동 처리 | Google Sheets 출고 기록과 BL+ESTNO+등급 매칭 → 홀딩 자동 차감 |

---

## 2. 디렉토리 구조

```
azy_firbase_web/
│
├── run_service.py              # 서비스 진입점: 파이프라인 + API 서버 동시 실행
├── api_server.py               # FastAPI REST API (port 8000)
├── CLAUDE.md                   # AI 어시스턴트용 프로젝트 가이드
│
├── pipeline/                   # 자동화 파이프라인
│   ├── scheduler.py            # APScheduler: 평일 08:00~17:00 1분 간격 실행
│   ├── crawler.py              # 병렬 HTTP 크롤링 + EDA 래퍼
│   ├── updater.py              # DataFrame → MySQL diff 업데이트 + 재고 변화 감지
│   ├── mysql_updater.py        # MySQLUpdater: INSERT/UPDATE/DELETE + 자동차감 + 이상처리
│   ├── mysql_db.py             # MySQL 연결 + 공통 쿼리 유틸리티
│   ├── sheets_reader.py        # Google Sheets 출고 기록 로더 (gspread)
│   ├── snapshot.py             # snapshot.pkl 로드/저장
│   ├── snapshot.pkl            # 마지막 파이프라인 상태 캐시 (자동 생성, gitignore)
│   └── logs/
│       └── pipeline.log        # 파이프라인 실행 로그 (UTF-8)
│
├── back_end/
│   ├── crawling_list.py        # HTTP 크롤링 (로그인 → 창고별 데이터 수집)
│   ├── crawling_handmade.py    # 비표준 사이트 수동 크롤링
│   ├── back_eda_main.py        # EDA 오케스트레이터 (list_eda)
│   ├── jns_eda.py              # 제니스(곤지암) 전용 EDA
│   ├── eda_ch_plz_cs.py        # CH·PLZ·CS 창고 EDA
│   ├── eda_else_df.py          # 기타 창고 EDA
│   ├── eda_standard.py         # 공통 EDA 유틸리티
│   ├── eda_common.py           # 공통 전처리 함수
│   ├── eda_added.py            # 추가 정제 로직
│   ├── eda_column.py           # 출력 컬럼 표준화
│   ├── replace_name.py         # 상품명 정규화 사전
│   ├── equal_df.py             # 기존 재고장과 신규 데이터 비교
│   ├── exception_safe.py       # EDA 함수 안전 래퍼
│   └── data/
│       ├── warehouse_list.xlsx # 창고 목록 및 로그인 정보
│       └── warehouse/          # 창고별 EDA 결과 및 비교 기준 파일
│
├── front_end/html/
│   ├── warehouse_main.html     # SPA 진입점
│   ├── warehouse_main.js       # 앱 초기화 진입점 (type="module")
│   ├── main.html               # 홈 화면
│   ├── css/
│   │   ├── warehouse_main.css  # 메인 스타일
│   │   └── main.css
│   └── js/
│       ├── api.js              # REST API 클라이언트 (fetch 래퍼)
│       ├── firebase.js         # 데이터 로드 + 5분 폴링 (이름은 레거시)
│       ├── firestoreService.js # CRUD 함수 (api.js 래퍼, 이름은 레거시)
│       ├── state.js            # 전역 상태 (allData, selectedItems, pendingChanges)
│       ├── table.js            # 테이블 렌더링
│       ├── panel.js            # 사이드 패널 (추가/수정/홀딩 카드)
│       ├── events.js           # DOM 이벤트 바인딩
│       ├── crud.js             # 비즈니스 로직 (holdingData, insertData, updateData)
│       ├── crud_history.js     # Undo 스택
│       ├── changes.js          # 변경사항 탭 (재고 감소 수동 처리)
│       ├── data_eda.js         # API 응답 → UI 정규화
│       ├── dom.js              # DOM 요소 캐시
│       ├── input_calculater.js # 홀딩 수량·중량 합계 계산
│       ├── actions.js          # 패널 모드 상수
│       └── ui.js               # Toast, Confirm 다이얼로그
│
├── scripts/                    # 서비스 관리 배치 파일
│   ├── manage_service.bat      # 서비스 start/stop/restart/status/logs
│   ├── update_and_restart.bat  # git pull + 서비스 재시작
│   ├── install_taskscheduler.bat # Windows 작업 스케줄러 등록
│   └── setup_windows.bat       # 초기 환경 설정
│
├── azycompany-2c80615785a2.json  # Google Sheets 서비스 계정 키 (gitignore)
├── requirements_pipeline.txt
└── README.md
```

---

## 3. 환경 요구사항

| 항목 | 버전 / 비고 |
|---|---|
| Python | 3.10 이상 (3.14 사용 중) |
| MySQL | 8.0 이상 |
| 주요 패키지 | `fastapi`, `uvicorn`, `pymysql`, `pandas`, `requests`, `apscheduler`, `openpyxl`, `gspread` |
| 브라우저 | ES 모듈 지원 (Chrome, Edge 최신) |
| OS | Windows 10/11 |

```bash
pip install fastapi uvicorn pymysql pandas requests apscheduler openpyxl gspread
```

---

## 4. 초기 설정

### 4-1. MySQL DB 생성

```sql
CREATE DATABASE azy_warehouse CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hyemi'@'localhost' IDENTIFIED BY '0943';
GRANT ALL PRIVILEGES ON azy_warehouse.* TO 'hyemi'@'localhost';
FLUSH PRIVILEGES;
```

**테이블 생성:** `pipeline/mysql_db.py`의 스키마 참고 또는 아래 실행

```sql
-- inventory: 크롤 행(수집일=날짜) + 홀딩 행(수집일='')
CREATE TABLE inventory ( ... );

-- holding_records: 홀딩 이력
CREATE TABLE holding_records ( ... );

-- pending_changes: 재고 감소 수동 처리 대기
CREATE TABLE pending_changes (id VARCHAR(255) PRIMARY KEY, data_json TEXT);

-- employees: 담당자 목록 (초기화 대상 아님)
CREATE TABLE employees (id VARCHAR(255) PRIMARY KEY, 이름 VARCHAR(100), 역할 VARCHAR(100));
```

### 4-2. Google Sheets 서비스 계정

출고 자동 차감 기능에 사용됩니다.

1. Google Cloud Console → 새 프로젝트 → **Google Sheets API** 사용 설정
2. 서비스 계정 생성 → **JSON 키 다운로드** → 프로젝트 루트에 저장
3. `pipeline/sheets_reader.py`의 `CRED_PATH` 업데이트
4. 출고 기록 Google Sheets에 서비스 계정 이메일을 **편집자**로 공유

### 4-3. 창고 목록 파일

`back_end/data/warehouse_list.xlsx` — 창고명, IP:Port, 로그인 ID/PW, 고객코드 포함.

---

## 5. 서비스 실행

### 5-1. 파이프라인 + API 서버 동시 실행

```powershell
$pythonExe = "C:\Users\OWNER\AppData\Local\Python\pythoncore-3.14-64\python.exe"
Start-Process $pythonExe -ArgumentList "run_service.py" `
    -WorkingDirectory "C:\Users\OWNER\.vscode\azy_firbase_web" -NoNewWindow
```

- **파이프라인:** 평일(월~금) 08:00~17:00, 1분 간격 자동 실행
- **API 서버:** `http://localhost:8000` (FastAPI, 백그라운드 스레드)
- **로그:** `pipeline/logs/pipeline.log`

```powershell
# 프로세스 확인 / 종료
Get-Process python* | Stop-Process -Force
```

### 5-2. 웹 접속

API 서버가 정적 파일도 서빙합니다:

```
http://localhost:8000/front_end/html/warehouse_main.html
```

외부 접속이 필요한 경우 ngrok 등 터널링 사용:
```bash
ngrok http 8000
```

### 5-3. DB 초기화 (재시작 시)

```python
# employees 제외 전체 초기화
DELETE FROM pending_changes;
DELETE FROM holding_records;
DELETE FROM inventory;
# pipeline/snapshot.pkl 삭제 후 서비스 재시작
```

---

## 6. 파이프라인 상세

### 6-1. 실행 흐름

```
scheduler.py::run_pipeline()
    ↓
CrawlerPool.crawl_all()          # 병렬 HTTP 크롤링
    ↓
CrawlerPool.normalize()          # back_eda_main.list_eda() EDA 정제
    ↓
Snapshot.load()                  # snapshot.pkl 로드
    ↓
MySQLUpdater.update_diff()
    ├── load_sheet_records()     # Google Sheets 오늘 탭 출고 기록 조회
    ├── _df_to_dict()            # 재고 변화 감지 + 자동/수동 분류
    ├── INSERT / UPDATE / DELETE # db_snapshot 기준 MySQL 반영
    ├── _apply_auto_deductions() # 시트 매칭 항목 holding 자동 차감
    ├── _write_pending_changes() # 시트 미매칭 감소 → pending_changes 기록
    └── _flag_holding_issues()   # 원본없음/수량초과 홀딩 자동 처리
    ↓
Snapshot.save(new_data)          # snapshot.pkl 갱신
```

### 6-2. `_df_to_dict()` — 재고 변화 감지

`snapshot.pkl`(이전 파이프라인 상태)과 현재 크롤 수량을 비교합니다.

```
prev_raw     = snapshot["재고"] + snapshot["holdingTotal"]  # 이전 크롤 총량
prev_nonhold = max(prev_raw - h_qty, 0)                     # 현재 홀딩 보정 후 non-hold

재고 증가: net_qty = prev_nonhold + diff
재고 감소:
  ├── 시트에 있음 → auto_list (변경사항 탭 미표시)
  │     ├── holding 레코드 있음: net_qty = prev_nonhold, holdingTotal -= diff
  │     └── holding 레코드 없음: net_qty = qty - h_qty (non-hold 직접 차감)
  └── 시트에 없음 → pending_list (변경사항 탭 수동 처리)
```

> **핵심:** auto_list 항목은 `holdingTotal`을 차감 후 값으로 pickle에 저장  
> → 다음 사이클에서 `prev_raw = net_qty + (h_qty - diff) = qty` → 재감지 없음

### 6-3. pk 체계

```
pk = "{코드}_{BL뒤4자리}_{식별번호뒤4자리}_{유통기한YYYYMMDD}"
     (특수문자 → _ 치환)

예시: 640O4P23_8600_1057_20260725
```

- 크롤 행의 `id` = `pk` = MySQL `inventory.id`
- 홀딩 행: `inventory.id` = UUID, `inventory.pk` = 원본 크롤 행의 pk
- 홀딩 레코드: `holding_records.pk` = 원본 크롤 행의 pk
- holding_sum 매칭은 pk 기준 → 상품명 변경에도 홀딩 유지

### 6-4. `snapshot.pkl`

- 마지막 파이프라인 출력 `{pk: {필드: 값}}` 딕셔너리
- `snapshot.pkl` 없으면 전체 INSERT로 시작
- 초기화 필요 시: 파일 삭제 후 서비스 재시작

---

## 7. MySQL 스키마

### 7-1. `inventory` 테이블

크롤 행과 홀딩 행이 공존합니다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | VARCHAR(255) PK | 크롤 행: pk와 동일. 홀딩 행: UUID |
| `pk` | VARCHAR(255) | 기본키. 홀딩 행은 원본 크롤 행의 pk |
| `상품명` | VARCHAR | |
| `브랜드` | VARCHAR | |
| `등급` | VARCHAR | |
| `ESTNO` | VARCHAR | EST 인증 번호 |
| `재고` | INT | 박스 수 (홀딩 차감 후 잔여 또는 홀딩 수량) |
| `BL` | VARCHAR | BL 번호 전체 |
| `창고` | VARCHAR | |
| `유통기한` | VARCHAR | YYYY-MM-DD |
| `중량` | FLOAT | 개당 중량(kg) |
| `평중` | FLOAT | 평균 중량(kg) |
| `출고일` | VARCHAR | 출고 예정일 |
| `홀딩` | VARCHAR | 홀딩 담당자명 |
| `상태` | VARCHAR | `없음` / `holding` |
| `메모` | TEXT | 사용자 메모 |
| `수집일` | VARCHAR | 크롤 행: YYYY-MM-DD. 홀딩 행: `''` |
| `holdingTotal` | INT | 해당 pk의 홀딩 수량 합계 (pickle 비교용) |
| `holdingRecordId` | VARCHAR | 연결된 holding_records.id |
| `이상` | VARCHAR | 홀딩 이상 감지 메모 |
| `원본재고` | INT | 이상 감지용 원본 수량 |

**크롤 행 vs 홀딩 행 구분:**

| 구분 | `상태` | `수집일` | `id` |
|---|---|---|---|
| 크롤 행 | `없음` | YYYY-MM-DD | pk |
| 홀딩 행 | `holding` | `''` | UUID |

### 7-2. `holding_records` 테이블

홀딩 이력 관리. `inventory` 홀딩 행의 `holdingRecordId`와 연결.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | VARCHAR(255) PK | `{pk}hold{N}` 형식 |
| `pk` | VARCHAR | 원본 크롤 행의 pk |
| `BL` | VARCHAR | |
| `ESTNO` | VARCHAR | |
| `등급` | VARCHAR | |
| `수량` | INT | 홀딩 수량 |
| `홀딩` | VARCHAR | 담당자명 |
| `출고일` | VARCHAR | 출고 예정일 |
| `메모` | TEXT | |

### 7-3. `pending_changes` 테이블

시트 미매칭 재고 감소 항목 (수동 처리 대기).

| 컬럼 | 타입 |
|---|---|
| `id` | VARCHAR(255) PK |
| `data_json` | TEXT (JSON) |

매 파이프라인 사이클마다 전체 교체 (해소된 항목 자동 삭제).

### 7-4. `employees` 테이블

담당자 목록. **절대 초기화 대상 아님.**

| 컬럼 | 타입 |
|---|---|
| `id` | VARCHAR(255) PK |
| `이름` | VARCHAR |
| `역할` | VARCHAR |

---

## 8. 홀딩 시스템

### 8-1. 개념

출고 예약 상태로 재고를 분리하는 기능.

```
[크롤 재고 100박스]
       ↓ holdingData(60박스)
[inventory 크롤 행: 재고=40] + [inventory 홀딩 행: 재고=60, 상태=holding]
                                [holding_records: 수량=60]
```

### 8-2. 홀딩 처리 흐름

```
holdingData(item, holdQty)
  ├── remainQty = item.qty - holdQty
  ├── remainQty > 0: updateItem(id, {재고: remainQty})  → 크롤 행 재고 감소
  └── remainQty = 0: deleteItem(id)                     → 크롤 행 삭제 (0박스 행 방지)
  └── insertItem({상태:"holding", 수집일:"", 재고: holdQty, ...})  → 홀딩 행 생성
  └── insertHoldingRecord({pk, BL, ESTNO, 등급, 수량, ...})       → holding_records 기록
  └── pushUndo({type:"holding", wasDeleted, originalData, ...})
```

### 8-3. 파이프라인과 홀딩의 관계

```python
h_qty = holding_records에서 pk 기준 수량 합계
net_qty = 크롤_수량 - h_qty      # 실제 표시 재고
# net_qty ≤ 0이면 크롤 행 스킵 (전량 홀딩)
```

파이프라인은 `수집일=''` 행을 건드리지 않으므로 홀딩 행은 크롤링에 의해 초기화되지 않습니다.

### 8-4. 홀딩 이상 자동처리 (`_flag_holding_issues`)

매 파이프라인 사이클에 자동 실행:

| 상황 | 처리 |
|---|---|
| 크롤에서 해당 pk 완전히 사라짐 (원본없음) | inventory 홀딩 행 + holding_records DELETE |
| holding 합계 > 크롤 수량 (수량초과) | 초과분을 작은 홀딩 행부터 차감, 0이면 DELETE |

### 8-5. Undo

```javascript
// undo 스택에 저장
pushUndo({
    type: "holding",
    wasDeleted: remainQty === 0,     // 전량홀딩이면 크롤 행이 삭제됨
    originalData: { ...item.raw },   // 전량홀딩 시 복구용 원본 데이터
    originalId, originalQty,
    holdingId, holdingRecordId
})

// undo 실행
wasDeleted ? insertItem(originalData) : updateItem(originalId, {재고: originalQty})
deleteItem(holdingId)
moveHoldingToHistory(holdingRecordId, "취소")
```

---

## 9. 출고 자동 차감 (Google Sheets)

### 9-1. 시트 형식

| 시트 | 설명 |
|---|---|
| 탭 이름 | `YYYY-MM-DD` (당일 날짜) |
| 컬럼 | `거래처`, `품목`, `브랜드`, `등급`, `EST`, `수량`, `BL`, `출고창고` |

시트에 기록된 행 = **무조건 홀딩 출고로 처리** (별도 홀딩 체크박스 없음).

### 9-2. 매칭 및 처리

```
시트 BL + ESTNO + 등급 → inventory 홀딩 행 + holding_records 탐색

매칭됨:
  inventory 홀딩 행 재고 -= diff
  holding_records 수량    -= diff
  net_qty(크롤 행) = prev_nonhold 유지  ← 감소분은 홀딩에서 처리

매칭 안 됨 (홀딩 없이 단순 출고):
  net_qty = 크롤수량 - h_qty  ← non-hold에서 직접 차감

→ 두 경우 모두 변경사항 탭에 미표시 (pending_list 기록 안 함)
```

### 9-3. 설정

```python
# pipeline/sheets_reader.py
SHEET_ID  = "1z7nYU9lfQT7d5boRwiU-zttwx90uVlUw2Y77Ydok6LY"
CRED_PATH = "azycompany-2c80615785a2.json"
```

---

## 10. 웹 UI 구조

### 10-1. 렌더링 흐름

```
[페이지 로드]
  bindEvents()          ← 모든 DOM 이벤트 등록
  initFirebase()        ← 더미 (MySQL 버전에서는 불필요)
  subscribeData()
    → fetchAllData()    ← GET /api/inventory
    → state.allData = [...]
    → renderTable()
    → renderSelectData()

[행 더블클릭]
  addSelectedItem()     ← 행 정규화 후 state.selectedItems 추가
  renderAll()

[홀딩 버튼]
  holdingData()         ← CRUD 처리
  5분 폴링에서 자동 갱신
```

### 10-2. 변경사항 탭

시트 기록 없이 크롤 재고가 감소한 항목을 수동 처리합니다.

- **non-hold에서 차감:** 시스템이 이미 반영 → pending_changes 레코드 삭제만
- **hold에서 차감:** non-hold 수량 복구 + holding 행 감소 + pending 삭제

자동 차감된 항목(시트 매칭)은 이 탭에 표시되지 않습니다.

### 10-3. 테이블 컬럼

| 컬럼 | 설명 |
|---|---|
| 선택 (체크박스) | 행 선택 |
| 상품명 | |
| 브랜드 | |
| 등급 | |
| ESTNO | |
| 재고 | 홀딩 차감 후 잔여 박스 수 |
| BL | |
| 창고 | |
| 유통기한 | |
| 평균중량 | |
| 메모 | |
| 사용 (✓) | 홀딩 행 완료 처리 버튼 |

출고일·홀딩 담당자는 행 호버 카드에 표시됩니다.

### 10-4. 행 색상

| 상태 | 색상 |
|---|---|
| 일반 (`없음`) | 기본 |
| 홀딩 (`holding`) | 파랑 |
| 선택됨 | 초록 |
| 동결 (`freeze`) | 보라 |
| 중단 (`stopped`) | 갈색 |
| 이동 (`moving`) | 주황 |

---

## 11. API 서버

`api_server.py` — FastAPI, port 8000.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/inventory` | 전체 재고 조회 (크롤 행 + 홀딩 행) |
| GET | `/api/employees` | 담당자 목록 |
| GET | `/api/pending-changes` | 수동 처리 대기 항목 |
| POST | `/api/inventory` | 재고 행 추가 |
| PUT | `/api/inventory/{id}` | 재고 행 수정 |
| DELETE | `/api/inventory/{id}` | 재고 행 삭제 |
| POST | `/api/holding-records` | 홀딩 레코드 추가 |
| PUT | `/api/holding-records/{id}` | 홀딩 레코드 수정 |
| DELETE | `/api/holding-records/{id}` | 홀딩 레코드 삭제 |
| GET | `/api/holding-count/{pk}` | pk 기준 홀딩 건수 조회 |
| POST | `/api/holding-records/{id}/history` | 홀딩 → 이력으로 이동 |
| DELETE | `/api/pending-changes/{id}` | pending 항목 삭제 |

웹 UI와 API 서버가 같은 origin에서 동작하므로 CORS 이슈 없음.

---

## 12. 트러블슈팅

### 파이프라인이 시작되지 않음

```powershell
# 기존 프로세스 확인 후 강제 종료
Get-Process python* | Stop-Process -Force
# snapshot.pkl이 손상된 경우 삭제
Remove-Item pipeline\snapshot.pkl
```

### 재고 수량 불일치

**원인 1:** snapshot.pkl과 MySQL 상태 불일치

```powershell
# snapshot.pkl 삭제 후 재시작 → 전체 재비교
Remove-Item pipeline\snapshot.pkl
```

**원인 2:** 홀딩 이상 (원본 없음 / 수량 초과)

자동으로 다음 파이프라인 사이클에 처리됩니다 (`_flag_holding_issues`).

### 자동 차감이 작동하지 않음

1. 파이프라인 로그에서 `[시트]` 라인 확인 — 시트 접속 성공 여부
2. `[재고감소-자동]` 로그 없으면 시트의 BL/ESTNO/등급이 크롤 데이터와 불일치
3. `[재고감소-pending]` 로그 있으면 시트에 해당 항목이 없는 것

### PowerShell에서 한국어 인코딩 깨짐

파일 내용 치환은 반드시 Bash `sed` 사용. `Get-Content | Set-Content`는 UTF-16으로 인코딩해 한국어가 깨집니다.

### `back_eda_main.py` 경로 오류

파일 내 `sys.path.append('C:\\Users\\ASUS\\...')` 하드코딩이 있습니다. 다른 PC에서 실행 시 수정 필요.
