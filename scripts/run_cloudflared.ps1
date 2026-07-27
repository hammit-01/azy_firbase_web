$logDir = Join-Path (Split-Path $PSScriptRoot -Parent) "pipeline\logs"

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000 2>&1 |
ForEach-Object {
    $_ | Out-File -Append -FilePath "$logDir\cloudflared.log" -Encoding utf8
    if ($_ -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [CLOUDFLARE] 접속 주소: $($matches[0])" |
            Out-File -Append -FilePath "$logDir\pipeline.log" -Encoding utf8
    }
}
