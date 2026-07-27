$logDir = Join-Path (Split-Path $PSScriptRoot -Parent) "pipeline\logs"
# 파이프라인과 API가 서로 다른 폴더(C:\warehouse-pipeline, C:\Users\OWNER\.vscode\azy_firbase_web)에서
# 각자 자기 pipeline.log에 기록하는 상태라, 어느 쪽을 보든 주소가 보이도록 둘 다에 남긴다.
$pipelineLogs = @(
    "$logDir\pipeline.log",
    "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\logs\pipeline.log"
)

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000 2>&1 |
ForEach-Object {
    $_ | Out-File -Append -FilePath "$logDir\cloudflared.log" -Encoding utf8
    if ($_ -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [CLOUDFLARE] 접속 주소: $($matches[0])"
        foreach ($log in $pipelineLogs) {
            if (Test-Path (Split-Path $log -Parent)) {
                $line | Out-File -Append -FilePath $log -Encoding utf8
            }
        }
    }
}
