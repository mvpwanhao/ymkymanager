#!/usr/bin/env pwsh
# ???????? Docker??
# 1) ?? git push
# 2) SSH ?????? scripts/server_git_pull_deploy.sh
#
# ???
#   .\scripts\deploy_via_git.ps1 -SshTarget wanhao@192.168.14.222 -RemoteCd "/home/wanhao/ymky_manager"
#   .\scripts\deploy_via_git.ps1 -SshTarget wanhao@192.168.14.222 -RemoteCd "/home/wanhao/ymky_manager" -NoPush

param(
    [Parameter(Mandatory = $true, HelpMessage = "SSH??? wanhao@192.168.14.222")]
    [string]$SshTarget,

    [string]$RemoteCd = "/home/wanhao/ymky_manager",
    [string]$GitRemote = "origin",
    [string]$Branch = "main",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

if (-not $NoPush) {
    Write-Host "git push ${GitRemote} ${Branch}" -ForegroundColor Cyan
    & git push $GitRemote $Branch
}

$bashLine = "cd `"$RemoteCd`" && chmod +x ./scripts/server_git_pull_deploy.sh && ./scripts/server_git_pull_deploy.sh"
Write-Host "ssh ? $bashLine" -ForegroundColor Cyan
ssh $SshTarget "bash -lc `"$bashLine`""

Write-Host "Done. Check http://192.168.14.222:8080" -ForegroundColor Green
