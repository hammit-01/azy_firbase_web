# 창고 재고 시스템 재시작. 예전/중복 스케줄 작업까지 전부 죽인 뒤
# 실제 쓰는 것만 새로 켠다 — 중복 실행으로 인한 이중 크롤링/이중 집계 사고를 막기 위함.
#
# 터널(CloudflaredWarehouseTunnel)은 기본적으로 건드리지 않는다 — quick tunnel이라
# 재시작할 때마다 공개 주소가 랜덤으로 바뀌는데, 코드 배포는 파이프라인/API
# 프로세스만 재시작하면 되고 터널까지 같이 죽일 이유가 없다. 터널 자체를
# 고쳤을 때만 -RestartTunnel 넘겨서 명시적으로 재시작.
param(
    [switch]$RestartTunnel
)

$liveTasks = @("창고재고파이프라인", "WarehouseAPI")
$legacyTasks = @("WarehousePipeline", "창고재고API서버", "창고재고ngrok")
$tunnelTask = "CloudflaredWarehouseTunnel"

$toStop = $liveTasks + $legacyTasks
if ($RestartTunnel) { $toStop += $tunnelTask }

foreach ($t in $toStop) {
    try { Stop-ScheduledTask -TaskName $t -ErrorAction Stop } catch {}
}

Start-Sleep -Seconds 3

Remove-Item "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\.service.lock" -ErrorAction SilentlyContinue
Remove-Item "C:\warehouse-pipeline\pipeline\.api.lock" -ErrorAction SilentlyContinue

$toStart = $liveTasks
if ($RestartTunnel) { $toStart += $tunnelTask }

foreach ($t in $toStart) {
    Start-ScheduledTask -TaskName $t
}

Start-Sleep -Seconds 5
Get-ScheduledTask -TaskName ($liveTasks + $legacyTasks + $tunnelTask) |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, LastRunTime, LastTaskResult

Write-Output "--- 현재 접속 주소 (안 바뀜, RestartTunnel 안 썼으면) ---"
Get-Content "C:\warehouse-pipeline\pipeline\logs\cloudflare_url.txt" -ErrorAction SilentlyContinue
