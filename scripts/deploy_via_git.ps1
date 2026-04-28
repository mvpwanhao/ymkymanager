#!/usr/bin/env pwsh
# Optional: git push -> SSH remote and run scripts/server_git_pull_deploy.sh (no Docker)
#
#   .\scripts\deploy_via_git.ps1 -SshTarget wanhao@192.168.x.x -RemoteCd "/home/wanhao/ymky_manager"
#   ... -GitRemote github -Branch main   # or -NoPush

param(
    [Parameter(Mandatory = $true, HelpMessage = "SSH login e.g. wanhao@192.168.x.x")]
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
