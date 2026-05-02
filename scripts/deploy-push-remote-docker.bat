@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM ------------------------------------------------------------------------------
REM Local: git push -> SSH remote: scripts/server_git_pull_deploy_docker.sh
REM        (pull, optional compose build, compose up -d)
REM Edit REMOTE_* / GIT_* below. Remote user needs docker/git without prompts.
REM PowerShell equiv: .\scripts\deploy_via_git.ps1 -Docker -SshTarget ... -Branch main
REM 说明：控制台使用 UTF-8（chcp 65001），与本文件 BOM-UTF8 编码一致可避免中文乱码。
REM ------------------------------------------------------------------------------

set "REMOTE_SSH=wanhao@192.168.14.222"
set "REMOTE_DEPLOY_SCRIPT=/home/wanhao/ymky_manager/scripts/server_git_pull_deploy_docker.sh"

set "GIT_REMOTE=origin"
set "GIT_BRANCH=main"

set "SKIP_PUSH="
if /i "%~1"=="-nopush" set "SKIP_PUSH=1"
if /i "%~1"=="/nopush" set "SKIP_PUSH=1"

cd /d "%~dp0.." || (
  echo ERROR: 无法切换到项目根目录 "%~dp0.."
  exit /b 1
)

echo [1] 仓库根目录: %CD%

if defined SKIP_PUSH (
  echo [2] 已 SKIP_PUSH — 跳过 git push。
) else (
  echo [2] git push %GIT_REMOTE% %GIT_BRANCH%
  git push %GIT_REMOTE% %GIT_BRANCH%
  if errorlevel 1 (
    echo ERROR: git push 失败（请先 git commit）。
    exit /b 1
  )
)

echo [3] SSH 远端部署: bash %REMOTE_DEPLOY_SCRIPT%
echo     DEPLOY_BRANCH=%GIT_BRANCH% GIT_REMOTE=%GIT_REMOTE%
ssh "%REMOTE_SSH%" "export GIT_REMOTE=%GIT_REMOTE% DEPLOY_BRANCH=%GIT_BRANCH% && bash %REMOTE_DEPLOY_SCRIPT%"
if errorlevel 1 (
  echo ERROR: 远端部署失败。
  exit /b 1
)

echo Done.
exit /b 0
