@echo off
cd /d "%~dp0"
docker compose --env-file .env.docker down
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess; if ($p.Name -eq 'node') { Stop-Process -Id $p.Id -Force } }"
echo SecureVault stopped. Your data is kept.
pause
