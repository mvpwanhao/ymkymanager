# 本地开发：热重载（保存 .py/.html/.css/.js 后自动重启）
# 用法（PowerShell，仓库根目录）:  .\scripts\dev.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Uvicorn http://127.0.0.1:8080  (reload on save)  Ctrl+C 停止"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
