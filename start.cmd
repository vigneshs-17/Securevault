@echo off
title SecureVault
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-securevault.ps1"
pause
