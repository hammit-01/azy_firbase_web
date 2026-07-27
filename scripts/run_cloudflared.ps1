$logDir = Join-Path (Split-Path $PSScriptRoot -Parent) "pipeline\logs"
# 파이프라인(.vscode\azy_firbase_web)과 API(C:\warehouse-pipeline)가 서로 다른 폴더에서
# 각자 자기 프로세스로 pipeline.log를 독점 잠금(exclusive lock)하고 있어 남의 pipeline.log에는
# append가 실패한다 — 대신 두 곳 모두에 별도 파일(cloudflare_url.txt)로 최신 주소만 남긴다.
$urlFiles = @(
    "$logDir\cloudflare_url.txt",
    "C:\Users\OWNER\.vscode\azy_firbase_web\pipeline\logs\cloudflare_url.txt"
)

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000 2>&1 |
ForEach-Object {
    $_ | Out-File -Append -FilePath "$logDir\cloudflared.log" -Encoding utf8
    if ($_ -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [CLOUDFLARE] 접속 주소: $($matches[0])"
        foreach ($f in $urlFiles) {
            if (Test-Path (Split-Path $f -Parent)) {
                try { $line | Out-File -FilePath $f -Encoding utf8 -ErrorAction Stop } catch {}
            }
        }
    }
}
