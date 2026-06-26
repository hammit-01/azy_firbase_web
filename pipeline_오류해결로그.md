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

**발생일**: 2026-06-26  
**발생 위치**: PowerShell에서 로그 조회 시

**증상**
```
李쎄퀬 ?ш퀬 ?뚯씠?꾨씪???쒕퉬???쒖옉
```

**원인**  
`pipeline.log`는 UTF-8로 저장되나, PowerShell `Get-Content` 기본값이 시스템 코드페이지(CP949) 사용.

**해결**  
```powershell
# 올바른 조회 방법
Get-Content "C:\warehouse-pipeline\pipeline\logs\pipeline.log" -Encoding UTF8 -Tail 50

# 실시간 모니터링
Get-Content "C:\warehouse-pipeline\pipeline\logs\pipeline.log" -Encoding UTF8 -Wait -Tail 20
```

**현재 상태**: 해결됨 ✓

---

## 상태 요약 (2026-06-26 기준)

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
