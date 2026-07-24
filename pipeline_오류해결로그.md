# 파이프라인 오류 해결 로그

> 실제 발생한 오류만 기록. 발생일시 · 증상 · 원인 · 해결 순서로 정리.

---

## #001 — Firestore 429 Quota Exceeded → Secondary 미전환 (구버전 코드)

**발생일**: 2026-06-26  
**발생 위치**: `C:\Users\OWNER\.vscode\azy_firbase_web` (구버전 updater.py)

**로그**
```
[WARNING] updater - Firestore 할당량 초과 - 이번 라운드 쓰기 스킵 (내일 자정 리셋)
```

**원인**  
구버전 `updater.py`가 Primary 할당량 초과 시 Secondary로 전환하지 않고 해당 라운드를 스킵하는 로직이었음.

**해결**  
`updater.py`를 이중화 로직으로 교체:
- Primary 429 → `_fallback_to_secondary()` 호출 → Secondary 전체 기록
- Secondary도 초과 시 라운드 스킵
- 23시간 후 Primary 복귀 자동 시도

**현재 상태**: 해결됨 ✓

---

## #002 — Firestore RetryError: Timeout 60s + 429 Quota Exceeded

**발생일**: 2026-06-26 15:09 ~ 15:17  
**발생 위치**: `C:\warehouse-pipeline`

**로그**
```
[ERROR] scheduler - 파이프라인 오류: Timeout of 60.0s exceeded, last exception: 429 Quota exceeded.
google.api_core.exceptions.RetryError: Timeout of 60.0s exceeded, last exception: 429 Quota exceeded.
grpc._channel._InactiveRpcError: RESOURCE_EXHAUSTED:Quota exceeded.
```

**원인**  
1. 오늘 하루 Primary Firestore 쓰기 할당량 소진
2. `C:\warehouse-pipeline` 첫 실행 → `snapshot.pkl` 없음 → 402건 전체를 쓰려 시도
3. google-api-core가 60초 동안 재시도 후 `RetryError`로 래핑해서 raise
4. 60초 동안 이전 job이 실행 중 → 다음 1분 스케줄 job skip

**해결 흐름**
```
15:16:45  [PRIMARY] 할당량 초과 감지
15:16:46  Primary 초과 → Secondary 전환 시작
15:16:46  ★ [SECONDARY] DB 전환 완료
15:16:47  [SECONDARY] 초기 전체 기록 374건 완료
15:17:13  스냅샷 복구: 374건 → 변경 없음 → 정상화
```

**재발 방지**  
- Secondary DB(`awhw-0001`) 크레덴셜이 실행 위치에 반드시 있어야 함
- `C:\warehouse-pipeline\awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json` ← 확인 필수
- 매번 `setup_windows.bat` 또는 `update_and_restart.bat` 실행 시 자동 복사됨

**현재 상태**: 해결됨 (Secondary 운영 중) ✓

---

## #003 — APScheduler max instances reached (job skipped)

**발생일**: 2026-06-26 15:13, 15:15, 15:17  
**발생 위치**: `C:\warehouse-pipeline`

**로그**
```
[WARNING] apscheduler.scheduler - Execution of job "run_pipeline" skipped: maximum number of running instances reached (1)
```

**원인**  
Firestore 429로 인해 job이 60초 이상 실행 → 다음 1분 스케줄이 겹쳐서 skip 처리됨.  
`max_instances=1, coalesce=True` 설정의 정상 동작.

**해결**  
별도 조치 불필요. 이전 job이 완료되면 다음 스케줄에 정상 실행됨.  
단, 60초 타임아웃 중에는 1~2회 skip 발생함.

**현재 상태**: 정상 동작 ✓

---

## #004 — 두 개 트리거 중복 실행

**발생일**: 2026-06-26 15:15 ~ 15:18  
**발생 위치**: `C:\warehouse-pipeline`

**로그**
```
Running job "run_pipeline (trigger: interval[0:01:00], ...)"
Running job "run_pipeline (trigger: or[cron[day_of_week='mon-fri'...], ...])"
```

**원인**  
이전 서비스(dev 폴더, `interval` 트리거)와 새 서비스(warehouse-pipeline, `cron` 트리거)가 동시에 실행됨.  
`max_instances=1`로 인해 실제 충돌은 없었으나 로그가 혼재됨.

**해결**  
이전 서비스 종료 후 새 서비스만 실행.  
작업 스케줄러에 하나의 태스크만 등록 유지.

**현재 상태**: 해결됨 ✓

---

## #005 — snapshot.pkl 없음 → 첫 실행 시 전체 쓰기 발생

**발생일**: 2026-06-26 15:15  
**발생 위치**: `C:\warehouse-pipeline` (최초 설치 후)

**로그**
```
[INFO] snapshot - 스냅샷 복구: 0건
[INFO] scheduler - 완료 | 총 402건 조회 | 변경 374건 | 69.0초 소요
```

**원인**  
`setup_windows.bat`으로 새 위치에 설치 시 `snapshot.pkl`이 없음.  
이전 데이터와 비교 불가 → 전체 데이터를 Firestore에 쓰려 시도.  
마침 오늘 할당량이 소진된 상태라 60초 타임아웃 발생.

**해결**  
Secondary 전환 후 374건 전체 기록 → 스냅샷 저장 → 이후 diff 방식으로 정상 운영.

**재발 방지**  
- 할당량 여유 있을 때 `setup_windows.bat` 실행 권장
- 또는 기존 `snapshot.pkl`을 새 위치에 복사:
  ```powershell
  Copy-Item "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\snapshot.pkl" "C:\warehouse-pipeline\pipeline\"
  ```

**현재 상태**: 해결됨 ✓

---

## #006 — manage_service.bat `net start/stop` 오류

**발생일**: 2026-06-26  
**발생 위치**: `scripts\manage_service.bat`

**증상**
```
> manage_service.bat start
The service name is invalid.
```

**원인**  
`manage_service.bat`이 Windows 서비스 명령어(`net start/stop`)를 사용.  
실제 태스크는 작업 스케줄러(`schtasks`)로 등록되어 있어 호환되지 않음.

**해결**  
`net start/stop` → `schtasks /run` / `schtasks /end` / `schtasks /query`로 교체.

```bat
:START
schtasks /run /tn %SERVICE_NAME%

:STOP
schtasks /end /tn %SERVICE_NAME%

:RESTART
schtasks /end /tn %SERVICE_NAME%
timeout /t 2 /nobreak >nul
schtasks /run /tn %SERVICE_NAME%

:STATUS
schtasks /query /tn %SERVICE_NAME% /fo LIST
```

**현재 상태**: 해결됨 ✓

---

## #007 — Secondary 크레덴셜 파일 누락 (warehouse-pipeline)

**발생일**: 2026-06-26  
**발생 위치**: `C:\warehouse-pipeline`

**증상**  
Primary 할당량 초과 시 Secondary 전환 불가.

**원인**  
`setup_windows.bat`의 `robocopy`가 프로젝트 파일만 복사.  
`.json` 크레덴셜 파일은 `.gitignore`에 등록되어 git에 없음.  
`C:\warehouse-pipeline`에 Secondary 크레덴셜 파일 없음.

**해결**  
수동 복사:
```powershell
Copy-Item "C:\Users\OWNER\.vscode\azy_firbase_web\awhw-0001-firebase-adminsdk-fbsvc-1af5d17c53.json" "C:\warehouse-pipeline\"
```

**재발 방지**  
`update_and_restart.bat` 또는 `setup_windows.bat` 실행 시 크레덴셜 파일도 함께 복사하는 단계 추가 필요.

**현재 상태**: 해결됨 ✓

---

## #008 — 작업 스케줄러 등록 시 Access Denied

**발생일**: 2026-06-26  
**발생 위치**: `scripts\install_taskscheduler.bat`

**증상**
```
ERROR: Access is denied.
```

**원인**  
`schtasks /create /rl HIGHEST` 명령은 관리자 권한 필요.  
일반 터미널에서 실행하면 거부됨.

**해결**  
PowerShell 또는 CMD를 **관리자 권한**으로 실행 후:
```powershell
schtasks /delete /tn WarehousePipeline /f
schtasks /create /tn WarehousePipeline /tr "\"C:\warehouse-pipeline\run_pipeline.bat\"" /sc ONSTART /ru "%USERDOMAIN%\%USERNAME%" /rl HIGHEST /f
schtasks /run /tn WarehousePipeline
```

**현재 상태**: 미등록 (관리자 권한으로 직접 실행 필요) ⚠️

---

## #009 — 파이프라인 로그 한글 깨짐

**발생일**: 2026-06-26 (최초), 2026-07-01 (근본 해결)  
**발생 위치**: PowerShell에서 로그 조회 시 / `pipeline/logs/pipeline.log`

**증상**
```
李쎄퀬 ?ш퀬 ?뚯씠?꾨씪???쒕퉬???쒖옉
```

**원인**  
`pipeline.log`는 UTF-8(BOM 없음)로 저장되나, PowerShell `Get-Content` 기본값이 시스템 코드페이지(CP949) 사용.

**해결 1 (임시)**: 조회 시 `-Encoding UTF8` 옵션 지정
```powershell
Get-Content ".\pipeline\logs\pipeline.log" -Encoding UTF8 -Tail 50
Get-Content ".\pipeline\logs\pipeline.log" -Encoding UTF8 -Wait -Tail 20
```

**해결 2 (근본, 2026-07-01 적용)**: `scheduler.py` FileHandler 인코딩을 `utf-8-sig`(BOM 포함)로 변경  
→ Windows 도구가 BOM을 보고 UTF-8로 자동 인식
```python
# 변경 전
logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
# 변경 후
logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8-sig"),
```

**현재 상태**: 해결됨 ✓

---

## #010 — Secondary DB 활성 상태 미복구 → 웹이 구버전 데이터 표시

**발생일**: 2026-06-30 14:55 → 발견 2026-07-01  
**발생 위치**: `front_end/html/js/firebase.js` / Secondary Firestore `_meta/active_db`

**증상**  
웹에 총 58행 / 5,802박스만 표시. Firestore Primary에는 491건 / 66,359박스 정상 존재.

**원인**  
2026-06-30 14:55에 Primary 할당량 초과 → `handleQuotaExceeded()`가 Secondary로 자동 전환.  
Secondary의 `_meta/active_db.active = "secondary"` 기록됨.  
이후 Primary에 새 데이터가 정상 업로드됐으나 웹은 Secondary(56건/5,309박스)를 계속 읽음.  
**Primary 복구 후 마커를 수동으로 되돌리는 운영 절차가 없었음.**

**해결**  
```python
db2.collection("_meta").document("active_db").set({
    "active": "primary",
    "switched_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
})
```

**재발 방지**  
Primary 복귀 확인 후 Secondary `_meta/active_db.active`를 "primary"로 되돌리는 절차 운영에 추가.

**현재 상태**: 해결됨 ✓

---

## #011 — JNS 다중 계정 크롤링 데이터 덮어쓰기 버그

**발생일**: 코드 작성 시점부터 (오랫동안 잠복)  
**발생 위치**: `back_end/crawling_list.py` 316번째 줄

**증상**  
JNS 크롤링 결과 40,630박스. 실제 창고 합계 44,208박스. 약 3,578박스 손실.

**원인**  
```python
# 버그 코드
if warehouse == "제니스(곤지암)":
    jns = pd.DataFrame(data)  # 매 계정 반복마다 덮어쓰기
```
JNS는 계정이 여러 개(일반, 통관분, 웹출고, 웹출고(통관분))이고, 각 계정이 서로 다른 서브창고(곤지암, 곤CS, 곤SWC, 곤대재 등)를 크롤링함.  
반복할 때마다 이전 결과를 덮어써서 마지막 계정 데이터만 남았음.  

**왜 오래 잠복했나**  
손실분(~3,578박스)을 `crawling_handmade()`의 Excel 수동 창고 데이터가 우연히 메워주고 있었음.  
총합이 비슷하게 유지되면서 버그가 가려짐. Excel 수동 창고를 주석처리하자 비로소 드러남.

**해결**  
```python
jns_list = []
# 반복 내부
if warehouse == "제니스(곤지암)":
    jns_list.append(data)  # 누적
# 반복 후
jns = pd.concat(jns_list, ignore_index=True) if jns_list else pd.DataFrame()
```

**현재 상태**: 해결됨 ✓

---

## #012 — drop_duplicates(BL번호, 재고수량)로 유효 데이터 700박스 손실

**발생일**: #011 수정 직후 발견  
**발생 위치**: `back_end/back_eda_main.py`

**증상**  
크롤링 44,132박스 → EDA 후 43,432박스. -700박스 손실.

**원인**  
```python
total_data.drop_duplicates(subset=["BL번호", "재고수량"])
```
원래 완전 중복 행 제거 목적이었으나, 여러 JNS 계정에서 동일 BL번호에 동일 재고수량이 다른 서브창고로 나오는 경우 유효 데이터가 삭제됨.  
#011 수정 전에는 계정 하나만 남았으므로 이 문제가 드러나지 않았음.

**해결**  
두 줄 모두 제거. pk 기준 합산(JNS 전용)이 이미 있으므로 별도 중복 제거 불필요.

**현재 상태**: 해결됨 ✓

---

## #013 — JNS 단독 모드 실행 시 eda_common / eda_added 빈 DataFrame 오류

**발생일**: 2026-07-01  
**발생 위치**: `back_end/eda_common.py`, `back_end/eda_added.py`

**증상**
```
KeyError: 'B/L NO식별번호'   # eda_common.py
KeyError: '규격단위중량'      # eda_added.py swc()
```

**원인**  
원래 설계: "항상 여러 창고를 크롤링하므로 final_df가 절대 비어있지 않다"는 암묵적 가정.  
JNS 단독 모드 실행 시 비JNS final_df가 빈 DataFrame → 열 접근 즉시 KeyError.  
`eda_added.py`의 각 창고 함수는 빈 때 `return`(None 반환)해서 `pd.concat` 시 TypeError 위험.

**해결**  
- `eda_common()`: 함수 진입부에 `if df.empty or "B/L NO식별번호" not in df.columns: return df` 추가  
- `eda_added.py` 9개 함수 전체: `return` → `return pd.DataFrame()` 로 통일

**현재 상태**: 해결됨 ✓

---

## #014 — 브랜드 non-breaking space로 인한 치환 미적용 (5 STAR 267 등)

**발생일**: 2026-07-01 (조사) — 잠복 기간 불명  
**발생 위치**: `back_end/replace_name.py`

**증상**  
`replace_name.py`에 `"5 STAR 267": "5 STAR"`, `"5 STAR 562": "5 STAR"` 등 매핑이 존재하나 Firestore에 여전히 `"5 STAR 267"` 그대로 업로드됨.

**원인**  
BeautifulSoup `get_text(strip=True)`가 HTML `&nbsp;`를 `\xa0`(U+00A0, non-breaking space)으로 변환.  
JNS 사이트 브랜드명에 `\xa0`이 포함되어 `"5 STAR\xa0267"` 형태로 저장됨.  
`pandas Series.replace()`는 정확한 문자열 일치만 적용하므로 일반 공백 `\x20`으로 작성된 키와 불일치.

**해결**  
`replace_name.py`에서 `.replace()` 호출 전 브랜드 컬럼 정규화 추가:
```python
df["브랜드"] = (
    df["브랜드"]
    .astype(str)
    .str.replace(' ', ' ', regex=False)  # non-breaking space → 일반 공백
    .str.replace(r'\s+', ' ', regex=True)     # 연속 공백 정리
    .str.strip()
    .replace({"nan": "", "None": ""})
)
```

**주의**: Edit 도구로 `\xa0` 문자 삽입 시 일반 공백으로 저장될 수 있음.  
파일 수정 후 hex 검증 필수:
```powershell
$bytes = [System.IO.File]::ReadAllBytes("back_end\replace_name.py")
$idx = 2700  # 해당 줄의 바이트 위치
($bytes[$idx..($idx+10)] | ForEach-Object { $_.ToString("X2") }) -join " "
# C2 A0 이 보여야 정상
```
→ 안전한 방법: Write 도구로 파일 전체 재작성 후 `' '` Python 유니코드 이스케이프 사용.

**현재 상태**: 해결됨 ✓

---

## #015 — 다중 run_service.py 동시 실행 → 박스 수 과다 기재

**발생일**: 2026-07-01 16:31 ~ 17:00  
**발생 위치**: 시스템 전체 (9개 프로세스 동시 실행)

**증상**  
원본 JNS 크롤링 데이터 ~43,684박스인데 웹에 47,978박스 표시.  
로그에 매 라운드 `[정규화 경고] 박스 수 변동: 43684 → 47421 (+3737박스)` 반복.

**로그 패턴**
```
[정규화 후] EDA: 393행 / 47421박스         ← 잘못된 프로세스 (정상: 373행 / 43684박스)
[정규화 경고] 박스 수 변동: 43684 → 47421 (+3737박스)
[SECONDARY] ↑20건(신규) ↻0건(갱신) ✕0건   ← 매 라운드 20건 추가 삽입
완료 | EDA 393건/47421박스 → Firestore 387건/47360박스 ★ 61박스 차이 | 변경 20건
```

**원인**  
1. PID 락 파일(`pipeline/.service.lock`) 구현 이전부터 실행 중이던 `run_service.py` 프로세스가 9개 동시 실행 중.  
2. `_acquire_lock()`은 새 프로세스만 차단하고 기존 프로세스를 종료하지 않음.  
3. 9개 중 1개 프로세스가 매 라운드 20행 +3,737박스를 여분으로 생성해 Firestore에 삽입.  
4. 다른 정상 프로세스들과 충돌하며 Firestore가 47,000박스대에서 수렴.

**해결**  
실행 중인 모든 파이프라인 프로세스 확인 → 전체 종료 → 1개만 재시작:
```powershell
# 현재 실행 중 프로세스 확인
Get-WmiObject Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*run_service*" } | Select-Object ProcessId, CommandLine

# 전체 종료 (PID 목록 수집 후)
$procIds = @(<pid1>, <pid2>, ...)
foreach ($procId in $procIds) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }

# 1개만 재시작
Start-Process python -ArgumentList "run_service.py" -WorkingDirectory "C:\Users\OWNER\.vscode\azy_firbase_web" -WindowStyle Hidden
```

**재발 방지**  
- 서비스 재시작 전 항상 위 `Get-WmiObject` 명령으로 기존 프로세스 수 확인.  
- PID 락은 새 프로세스 중복 실행만 막으므로, 강제 종료(`Stop-Process -Force`) 후 락 파일이 남아있으면 수동 삭제:
  ```powershell
  Remove-Item "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\.service.lock" -ErrorAction SilentlyContinue
  ```
- Firestore 박스 수는 다음 크롤링 라운드(최대 1분)에 자동 정상화됨.

**현재 상태**: 해결됨 ✓ (2026-07-01 17:26, 단일 프로세스 PID 14528 실행 중)

---

## #016 — eda_standard 이후 생성된 "냉장돈목잡" → replace_name 치환 미적용

**발생일**: 2026-07-02  
**발생 위치**: `back_end/back_eda_main.py` (list_eda 실행 순서), 비JNS 창고 데이터

**증상**  
`replace_name`에 `"냉장돈목잡": "냉장목살"` 매핑이 있음에도 Firestore에 계속 "냉장돈목잡"으로 저장됨.  
파이프라인을 재시작하고 코드 배포 후에도 snapshot/Firestore 모두 "냉장돈목잡" 유지.

**원인**  
JNS 사이트 크롤 결과의 `수탁품` 값이 "냉장돈목잡\xa0"(NBSP) 또는 " 냉장돈목잡 " 형태의 trailing/leading whitespace를 포함.  
`pandas Series.replace(dict)` 는 exact match → "냉장돈목잡\xa0" ≠ "냉장돈목잡" → 치환 실패.  
이후 `_df_to_dict`의 `.strip()` 이 whitespace를 제거하므로 snapshot/Firestore에는 "냉장돈목잡"으로 저장되어, 언제나 prev == new → diff 미감지.

**해결**  
`replace_name.py` 수탁품/상품명 컬럼 replace 전에 `.astype(str).str.strip()` 추가:
```python
for _col in ("수탁품", "상품명"):
    if _col in df.columns:
        df[_col] = df[_col].astype(str).str.strip().replace(_name_map)
```

**재발 방지**  
- `replace_name` 내 모든 컬럼 치환은 strip 후 replace.
- 브랜드 컬럼은 이미 `.str.replace(' ', ...)` 처리 중.

**현재 상태**: 해결됨 ✓ (2026-07-02, 파이프라인 재시작 후 적용)

---

## #017 — drop_duplicates() 3중 잔존 → 대재 창고 중복 로트 박스 손실 (재발, #012 동일 유형)

**발생일**: 2026-07-20  
**발생 위치**: `pipeline/crawler.py` (`_crawl_single_row`), `back_end/eda_added.py` (`daejae`), `back_end/back_eda_main.py` (`list_eda` azy_data 병합부)

**증상**  
대재 창고 BL `OOLU2325409782`(뒷자리 9782)가 실제 사이트에는 10박스 로트가 2줄(총 20박스) 있는데, `azy_inventory`에는 1행·재고 10박스만 저장됨. DB 조회 결과 해당 BL은 정확히 1건뿐이었고, 원본재고=10으로 홀딩 차감도 아니었음.

**원인**  
#012에서 JNS 한정으로 제거했던 `drop_duplicates()`가 이후 MySQL 파이프라인(`1d8f404`, 2026-06-24) 리팩터링 때 **다른 3곳에 새로 생겨** 있었음:
1. `pipeline/crawler.py:66` — 크롤 직후, 창고 구분 없이 원본 행 전체에 `data.drop_duplicates()` (모든 창고 공통, JNS도 `crawl_one()`으로 이 경로를 탐)
2. `back_end/eda_added.py`의 `daejae()` — 원본 컬럼 기준 `drop_duplicates()`
3. `back_end/back_eda_main.py`의 `list_eda()` — `azy_data` 병합 후 `drop_duplicates()` (중량까지 같으면 구분 불가)

같은 상품·BL·유통기한·중량의 서로 다른 로트가 재고수량까지 우연히 같으면(이번 케이스: 10=10) 세 지점 중 어디서든 완전 동일 행으로 취급되어 한쪽이 통째로 사라짐. 뒤 단계(`scheduler.py`의 `_upload_azy()`)에 uid 기준 재고 합산 로직이 이미 있었지만, 그 앞에서 행이 먼저 지워지므로 합산할 대상 자체가 없었음.

**해결**  
세 지점 모두 "행 삭제" 대신 "수량 합산"으로 교체:
- `crawler.py:66`: `drop_duplicates()` 제거 (주석만 남김, 뒷단 합산에 위임)
- `eda_added.py daejae()`: `drop_duplicates()` 제거, 단순 `.copy()`로 대체
- `back_eda_main.py list_eda()`: `azy_data.drop_duplicates()` → `재고수량` 제외 전체 컬럼 `groupby(dropna=False)` 후 `재고수량` sum으로 교체 (JNS `pk` 합산과 동일 패턴)

**재발 방지**  
- 이 코드베이스에서 `drop_duplicates()`는 원칙적으로 금지. 중복 로트 병합은 반드시 "식별 컬럼 groupby + 수량 컬럼 sum" 패턴만 사용 (JNS pk 합산이 표준 예시).
- 새 크롤링/EDA 경로를 추가할 때 `git grep -n "drop_duplicates"` 로 우선 점검.
- 타창고 EDA(`eda_added.py`의 huichang/hyosung/eastbelly/aurora/sinu/samil/beige/swc, `eda_else_df.py`의 kd/ki/sjn/dch/hl)에도 동일한 `data.drop_duplicates()` 패턴이 남아있어 잠재적으로 같은 버그를 안고 있음 — 아직 미수정, 필요 시 동일하게 groupby+sum으로 교체할 것.

**현재 상태**: daejae 경로만 해결됨 ✓ (2026-07-20). 나머지 타창고 함수들은 동일 패턴 잔존 — 미해결 ⚠️

---

## #018 — crawling_handmade() 로그인 미가드 → 사이클 전체 실패, 효성냉장 등 타창고 데이터 MySQL 미반영

**발생일**: 2026-07-21  
**발생 위치**: `back_end/crawling_handmade.py` (`_ecms_fetch_cached`, `kyunu_eda`)

**증상**  
효성냉장을 `warehouse_list.xlsx`에서 활성화(ip포트 채움)한 직후 첫 파이프라인 사이클에서 효성냉장 8건이 정상 크롤·EDA까지 됐는데도 MySQL(`azy_inventory`)에는 반영 안 됨.

```
2026-07-21 09:46:08 crawler - ✓ 효성냉장: 8건
...
2026-07-21 09:48:33 [ERROR] scheduler - 파이프라인 오류: HTTPConnectionPool(host='localhost', port=50117): Read timed out. (read timeout=120)
  ...back_end/crawling_handmade.py:126 in _ecms_fetch_cached → _ecms_login(driver, base_url, user, pw)
  ...back_end/crawling_handmade.py:187 in korea_eda (고려냉장 로그인 중 헤드리스 Chrome 응답 없음)
```

**원인**  
`_ecms_fetch_cached()`(고려/유상/미빙냉장 공용)와 `kyunu_eda()`(견우오아시스)에서 캐시된 드라이버가 없을 때 최초 로그인 호출(`_ecms_login()` / `_kyunu_login()`)이 `try/except`로 감싸여 있지 않았음. 재시도 단계의 조회(`_krcs_fetch_instock`/`_kyunu_do_fetch`)만 예외를 삼키고, 로그인 자체가 타임아웃/예외를 던지면 그대로 `crawling_handmade()` → `list_eda()` → `crawler.normalize()` → `run_pipeline()`까지 전파됨.

`list_eda()`는 `crawling_handmade()` 호출 전에 이미 `added_df`(효성 포함 8개 창고)·`six_df`·`ch/plz/cs/irn`을 전부 EDA까지 끝낸 상태였지만, 마지막에 `hand_df = crawling_handmade()`에서 예외가 터지면서 `list_eda()`가 `return` 하기 전에 함수 전체가 죽어 **그 사이클에서 이미 완성된 azy_data 전체(효성 포함)가 MySQL에 한 번도 안 쓰이고 통째로 버려짐**.

1분 간격 재시도 스케줄 덕분에 다음 사이클(90.6초 소요, 헤드리스 Chrome이 이번엔 응답)에서 저절로 복구되어 효성냉장 데이터가 들어가긴 했으나, 근본 원인은 미수정 상태였음.

**해결**  
`_ecms_fetch_cached()`와 `kyunu_eda()`의 로그인 호출부 전체를 최상위 `try/except`로 감싸 실패 시 빈 리스트/빈 DataFrame 반환하도록 수정. 해당 사이트 하나의 로그인 실패가 같은 사이클의 다른 타창고 데이터까지 물귀신처럼 날리지 않게 격리.

**재발 방지**  
- 새 수동 크롤링 사이트를 `crawling_handmade.py`에 추가할 때 로그인 호출은 반드시 함수 전체를 감싸는 `try/except` 안에 있어야 함(조회부만 감싸는 걸로는 부족).
- `crawling_handmade()`는 4개 사이트를 한 번에 `pd.concat()`하므로, 한 사이트 함수가 예외를 던지면 나머지 사이트도 같이 실행 안 됨 — 원인은 이번에 잡았지만 구조적으로는 여전히 한 함수라도 새로 예외를 던지면 재발 가능한 지점.

**현재 상태**: ✓ 해결 (2026-07-21)

---

## 상태 요약 (2026-07-02 기준)

| # | 오류 | 상태 |
|---|------|------|
| 001 | Secondary 미전환 (구코드) | ✓ 해결 |
| 002 | Firestore 429 할당량 초과 | ✓ Secondary 자동 전환됨 |
| 003 | APScheduler job skip | ✓ 정상 동작 |
| 004 | 트리거 중복 실행 | ✓ 해결 |
| 005 | snapshot 없음 → 전체 쓰기 | ✓ 해결 |
| 006 | manage_service.bat net 명령 오류 | ✓ 해결 |
| 007 | Secondary 크레덴셜 누락 | ✓ 해결 |
| 008 | 작업 스케줄러 Access Denied | ⚠️ 관리자 권한 필요 |
| 009 | 로그 한글 깨짐 | ✓ 해결 (UTF8 옵션) |
| 010 | Secondary 활성 미복구 → 웹 구버전 표시 | ✓ 해결 |
| 011 | JNS 다중 계정 덮어쓰기 → 3,578박스 손실 | ✓ 해결 |
| 012 | drop_duplicates → 유효 데이터 700박스 손실 | ✓ 해결 |
| 013 | JNS 단독 모드 시 빈 DataFrame KeyError | ✓ 해결 |
| 014 | 브랜드 NBSP → 치환 미적용 (5 STAR 267 등) | ✓ 해결 |
| 015 | 다중 프로세스 동시 실행 → 박스 수 과다 (+3,737박스) | ✓ 해결 |
| 016 | eda_standard 냉장_mask가 replace_name 이후 "냉장돈목잡" 생성 → 치환 미적용 | ✓ 해결 |
| 017 | drop_duplicates() 3중 잔존 → 대재 중복 로트 박스 손실 (#012 재발) | ⚠️ daejae만 해결, 타창고 잔존 |
| 018 | crawling_handmade() 로그인 미가드 → 사이클 전체 실패, 타창고 MySQL 미반영 | ✓ 해결 |

---

## 현재 운영 상태 (2026-06-26 15:18~)

```
활성 DB       : Secondary (awhw-0001)
Primary 복귀  : 자정(00:00) 리셋 → 23시간 후 자동 시도
크롤링        : 제니스(곤지암) 402건 / 13~14초 소요
스냅샷        : 374건 정상 보유
스케줄        : 평일 08:00~17:00, 1분 간격
```

```powershell
# 현재 운영 상태 빠른 확인
Get-Content "C:\warehouse-pipeline\pipeline\active_db.json"
Get-Content "C:\warehouse-pipeline\pipeline\logs\pipeline.log" -Encoding UTF8 -Tail 10
```
