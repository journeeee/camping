# 로컬 PC 에서 상시 감시 (GitHub Actions 5분 제한보다 촘촘하게 돌리고 싶을 때)
# 사용:  powershell -ExecutionPolicy Bypass -File scripts\watch_loop.ps1 -IntervalSec 120
# 알림을 받으려면 먼저 환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (또는 DISCORD_WEBHOOK_URL) 를 설정하세요.
param([int]$IntervalSec = 120)
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "캠핑 빈자리 감시 시작 (간격 ${IntervalSec}초). 중지: Ctrl+C"
while ($true) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "---- $ts"
    python -m watcher run
    Start-Sleep -Seconds $IntervalSec
}
