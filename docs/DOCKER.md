# Docker 部署（局域网 / 小主机）

在 **Ubuntu Server**（或任意已装 Docker 的主机）上，将本目录作为项目根，`data/`、`runtime` 等与单机运行一致落在卷里。

若你最终选择 **无 Docker 直部署**，见 [DEPLOY_SYNC.md](./DEPLOY_SYNC.md)（本机 `git push`，服务器自动 `pull + restart`）。

## 1. 小主机上安装 Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-jammy}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
# 重新登录 SSH 使用户组生效，或临时 newgrp docker
```

验证：`docker --version`、`docker compose version`

也可在本仓库根目录用脚本替代手工 apt（需 root）：

```bash
sudo bash scripts/server_install_docker_ubuntu.sh
```

## 1b. 从 systemd + venv 迁到 Docker（服务器已在跑旧方式）

假定项目仍在例如 `/home/<user>/ymky_manager`，且 `.env`、`data/` 已就绪：

1. 拉最新代码：`git pull origin main`
2. 一次性安装 Docker：`sudo bash scripts/server_install_docker_ubuntu.sh`
3. **同一 SSH** 会话内激活 docker 组成员：`newgrp docker`（或重新登录 SSH）
4. 停止旧服务并用 Compose 拉起：`bash scripts/server_migrate_systemd_to_docker.sh`
5. 若使用 cron 自动更新，把任务里的 `server_git_pull_deploy.sh` 改成 `server_git_pull_deploy_docker.sh`
6. 本机手动触发远端更新（PowerShell）：`.\scripts\deploy_via_git.ps1 -Docker -SshTarget <user>@<server-ip>`

`ymky` systemd 单元会在迁移时被 `disable`；勿与容器同时监听 `8080`。

## 2. 放置项目与小主机对齐

任选其一：

- `git clone` / `scp` / `rsync`，使服务器上路径类似 `~/ymky_manager`（根目录下有 `Dockerfile`、`app/`、`docker-compose.yml` 等）。
- 保证存在 **`data/`**（可空）；首次上线可将 `sjcl.xlsx`、`nybb.xlsx` 放入 `data/`（报表模板）。

## 3. 配置 `.env`

```bash
cd ~/ymky_manager   # 按你的实际路径
cp .env.example .env
nano .env
```

必填至少：

- **`YMKY_SECRET_KEY`**：不少于 16 位随机字符串。
- 若设置 **`YMKY_TRUSTED_HOSTS`**：须包含局域网访问时用到的 **主机名或 IP（不含端口）**，例如局域网用 IP 打开时：

```env
YMKY_TRUSTED_HOSTS=<server-ip>,localhost,127.0.0.1
```

不设置 `YMKY_TRUSTED_HOSTS`（留空）时，不进行 Host 校验，一般也可在纯内网调试。

若在构建阶段拉取 **`python:3.12-slim-bookworm`** 或 **PyPI** 经常超时，可参考：

- **Docker Hub**：在宿主机配置 `/etc/docker/daemon.json` 的 `registry-mirrors`（如 DaoCloud 镜像），再 `sudo systemctl restart docker`。本机已按此方式做过一次。
- **容器内 Debian/apt**：`Dockerfile` 已在 **`apt-get update`** 前将默认源换为 **清华大学 Debian 镜像**（`mirrors.tuna.tsinghua.edu.cn`），减轻 **`deb.debian.org` 过慢**导致的 `RUN apt-get install` 卡死。若在**海外**构建，可去掉或改回该替换逻辑。
- **PyPI**：`docker-compose.yml` 已为 **`build.args.PIP_INDEX_URL`** 默认指定清华源；海外环境可改回 `https://pypi.org/simple` 或直接编辑 `Dockerfile` 的默认值。

## 4. 构建并启动

```bash
docker compose build
docker compose up -d
docker compose logs -f   # 看日志；Ctrl+C 退出跟日志
docker compose ps
```

应用在容器内监听 `0.0.0.0:8080`，映射为 **`主机:8080`**。

**Kaleido 导出 Excel（图表 PNG）**：`docker-compose.yml` 为 **`ymky`** 配置了 **`shm_size: "512mb"`**（过小会导致内置 Chromium 截图失败）。变更 Compose 后须 **`docker compose up -d --force-recreate ymky`** 才会应用到已存在容器。

### 4b. 构建缓存：会不会每次部署都重装 apt / pip？

**一般不会。** BuildKit/经典构建都会**按层缓存**：只要 **`Dockerfile` 里靠前的行**、**`requirements.txt`**、会影响 build 的 **`docker-compose.yml` 片段**等没有变，前面的 **`RUN apt-get`、`RUN pip install`** 层会直接复用，**不会每次都重新下载安装**。你频繁改 **`app/`、`templates/`、`static/`** 时，通常只会重建最上面几层。若使用了 **`docker compose build --no-cache`**、删掉缓存或改过「更靠前」的 `Docker`，才会整段重跑。

## 5. 局域网访问

同一 LAN 的设备浏览器打开：

```text
http://<server-ip>:8080
```

（若小主机 IP 变化，改用实际 IP；端口若在 `docker-compose.yml` 里改过，同步改端口。）

健康检查：`http://<server-ip>:8080/health`。

## 6. 防火墙（若启用 UFW）

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8080/tcp
sudo ufw enable
sudo ufw status
```

## 7. 常用运维命令

```bash
docker compose restart
docker compose down
docker compose up -d --build
docker compose exec ymky bash   # 进容器 Shell（服务名 ymky）
```

## 8. PostgreSQL / 可选数据库在宿主机上

若在 **同一台 Ubuntu** 上另装 Postgres，容器中 `DATABASE_URL` 可把 host 写成 **宿主机局域网 IP** 或小网桥地址（Linux 常为 `172.17.0.1`）；以你实际连通性为准。勿把 `localhost` 当作「宿主机上的数据库」除非你使用 `extra_hosts`/host 网关网络模式。

---

外网穿透：**Docker Compose profile `cloudflared`** 运行官方 `cloudflared`（见 **`docs/CLOUDFLARE_TUNNEL.md`**，Zero Trust Ingress 后端填 **`http://ymky:8080`**）；备选 **Sakura**，见 **`docs/SAKURA_TUNNEL.md`**。
