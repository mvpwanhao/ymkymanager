# =====================================================================
# Yunmei Mining - Production Mgmt System: Git offline backup
# Copyright (c) 2026-2027 Wan Hao. All rights reserved.
#
# Purpose:
#   Pack the entire repository (all branches + all tags) into a single
#   .bundle file for off-site / off-disk safekeeping. If the dev machine
#   is lost, restore via:  git clone <file>.bundle ymky_manager
#
# Usage:
#   .\scripts\backup_bundle.ps1
#   .\scripts\backup_bundle.ps1 -DestDir 'E:\my_backup'
#   .\scripts\backup_bundle.ps1 -KeepLast 5
# =====================================================================

[CmdletBinding()]
param(
    [string]$DestDir  = 'D:\backup\ymky_manager',
    [int]   $KeepLast = 10
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    $here = Split-Path -Parent $PSCommandPath
    Push-Location $here
    try {
        $root = (& git rev-parse --show-toplevel) 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $root) {
            throw "Not inside a git repo: $here"
        }
        return $root.Trim()
    }
    finally { Pop-Location }
}

$repoRoot = Resolve-RepoRoot
$repoName = Split-Path -Leaf $repoRoot
Set-Location $repoRoot

if (-not (Test-Path $DestDir)) {
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
}

Write-Host "==> Repo  : $repoRoot"
Write-Host "==> Dest  : $DestDir"

Write-Host "==> Running git fsck ..."
& git fsck --no-progress --strict
if ($LASTEXITCODE -ne 0) { throw "git fsck failed" }

$describe = (& git describe --tags --always --dirty) 2>$null
if (-not $describe) { $describe = (& git rev-parse --short HEAD) }
$describe  = ($describe -replace '[\\/:*?"<>|]', '_').Trim()
$timestamp = Get-Date -Format 'yyyyMMdd-HHmm'
$bundlePath = Join-Path $DestDir "${repoName}_${describe}_${timestamp}.bundle"

Write-Host "==> Creating bundle: $bundlePath"
& git bundle create $bundlePath --all
if ($LASTEXITCODE -ne 0) { throw "git bundle create failed" }

Write-Host "==> Verifying bundle ..."
& git bundle verify $bundlePath
if ($LASTEXITCODE -ne 0) { throw "git bundle verify failed" }

$size   = (Get-Item $bundlePath).Length
$sizeMB = [math]::Round($size / 1MB, 2)
Write-Host ("==> Done  ({0} MB): {1}" -f $sizeMB, $bundlePath)

if ($KeepLast -gt 0) {
    $all = Get-ChildItem -Path $DestDir -Filter "${repoName}_*.bundle" |
           Sort-Object LastWriteTime -Descending
    if ($all.Count -gt $KeepLast) {
        $toDelete = $all | Select-Object -Skip $KeepLast
        Write-Host ("==> Rotating: keep newest {0}, delete {1}" -f $KeepLast, $toDelete.Count)
        foreach ($f in $toDelete) {
            Write-Host "    delete $($f.Name)"
            Remove-Item $f.FullName -Force
        }
    }
}

Write-Host ""
Write-Host "Restore command (in case dev machine is lost):"
Write-Host "  git clone `"$bundlePath`" ymky_manager_restored"
