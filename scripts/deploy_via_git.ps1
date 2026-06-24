#!/usr/bin/env pwsh
# Optional: git push -> SSH remote and run server deploy hook
#
#   .\scripts\deploy_via_git.ps1 -SshTarget <user>@<server-ip> -RemoteCd "/home/<user>/ymky_manager"
#   ... -Docker   # remote: scripts/server_git_pull_deploy_docker.sh
#   ... -GitRemote github -Branch main   # or -NoPush

param(
    [Parameter(Mandatory = $true, HelpMessage = "SSH login e.g. <user>@<server-ip>")]
    [string]$SshTarget,

    [string]$RemoteCd = "/home/<user>/ymky_manager",
    [string]$GitRemote = "origin",
    [string]$Branch = "main",
    [switch]$NoPush,
    [switch]$Docker
)

$ErrorActionPreference = "Stop"

if (-not $NoPush) {
    Write-Host "git push ${GitRemote} ${Branch}" -ForegroundColor Cyan
    & git push $GitRemote $Branch
}

# Use absolute path (no rely on login shell cwd); script self-cd's to repo root
$hook = if ($Docker) { "server_git_pull_deploy_docker.sh" } else { "server_git_pull_deploy.sh" }
$deploySh = "$RemoteCd/scripts/$hook".Replace("\", "/")
Write-Host "ssh: bash $deploySh" -ForegroundColor Cyan
ssh $SshTarget "bash `"$deploySh`""

Write-Host "Done. Check http://<server-ip>:8080" -ForegroundColor Green
