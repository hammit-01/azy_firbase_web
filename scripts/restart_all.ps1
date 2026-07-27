# 창고 재고 시스템 전체 재시작. 예전/중복 스케줄 작업까지 전부 죽인 뒤
# 실제 쓰는 3개(파이프라인/API/터널)만 새로 켠다 — 중복 실행으로 인한
# 이중 크롤링/이중 집계 사고를 막기 위함.

$liveTasks = @("창고재고파이프라인", "WarehouseAPI", "CloudflaredWarehouseTunnel")
$legacyTasks = @("WarehousePipeline", "창고재고API서버", "창고재고ngrok")

foreach ($t in $liveTasks + $legacyTasks) {
    try { Stop-ScheduledTask -TaskName $t -ErrorAction Stop } catch {}
}

Start-Sleep -Seconds 3

Remove-Item "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\.service.lock" -ErrorAction SilentlyContinue
Remove-Item "C:\warehouse-pipeline\pipeline\.api.lock" -ErrorAction SilentlyContinue

foreach ($t in $liveTasks) {
    Start-ScheduledTask -TaskName $t
}

Start-Sleep -Seconds 5
Get-ScheduledTask -TaskName ($liveTasks + $legacyTasks) |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, LastRunTime, LastTaskResult
