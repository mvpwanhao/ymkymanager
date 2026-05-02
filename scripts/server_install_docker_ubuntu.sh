#!/usr/bin/env bash
# Ubuntu: 安装 Docker Engine + Compose 插件（与 docs/DOCKER.md 一致）
#
#   sudo bash scripts/server_install_docker_ubuntu.sh
#
# 装完后请将部署用户加入 docker 组（本脚本已对 SUDO_USER 执行 usermod）；
# 当前 SSH 会话内可用: newgrp docker  或  sg docker -c 'docker compose version'

set -euo pipefail

# shellcheck source=/dev/null
. /etc/os-release
DEB_CODENAME="${VERSION_CODENAME:-jammy}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 或 sudo 运行: sudo bash $0"
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${DEB_CODENAME} stable" \
  >/etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

DOCKER_USER="${SUDO_USER:-$USER}"
if [[ -n "$DOCKER_USER" && "$DOCKER_USER" != root ]]; then
  usermod -aG docker "$DOCKER_USER"
  echo "已将用户 '$DOCKER_USER' 加入 docker 组。新开 SSH 或使用: newgrp docker"
fi

docker --version
docker compose version
