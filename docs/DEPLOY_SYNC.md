# 本地开发 → 直部署到服务器（无 Docker）

目标：本机推到 **GitHub**；Ubuntu 服务器 `git clone` / `git pull` 后以 `venv` + `uvicorn` + `systemd` 常驻运行。

> 默认中央仓库：**[mvpwanhao/ymkymanager](https://github.com/mvpwanhao/ymkymanager)**（克隆地址见下文「服务器一次性准备」）。
>
> 适用：**不采用 Docker**，在 Ubuntu 上直接运行 Python。

---

## 推荐工作流

```text
本机：git commit → git push origin main（GitHub）
                          ↓
服务器：git pull（cron 或手动）→ 若依赖变更则 pip install → systemctl restart ymky
```

- 服务器上长期保留各自的 `.env` 与真实 `data/`，不要被本机整目录覆盖。
- 下文默认用户名 **wanhao**，目录 **`/home/wanhao/ymky_manager`**；IP 按需替换。

---

## 服务器一次性准备

### 0）系统依赖（Ubuntu）

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv
```

防火墙若开启，按需放行 `8080`（示例）：`sudo ufw allow 8080/tcp`。

### 1）从 GitHub 克隆并创建虚拟环境

**推荐使用 HTTPS（公开仓库可读，无须 GitHub SSH 密钥）：**

```bash
git clone https://github.com/mvpwanhao/ymkymanager.git /home/wanhao/ymky_manager
cd /home/wanhao/ymky_manager
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

**若已在 GitHub 为服务器配置了 Deploy key（或本机 SSH 密钥），可用 SSH URL：**

```bash
git clone git@github.com:mvpwanhao/ymkymanager.git /home/wanhao/ymky_manager
```

（远端名默认 `origin`，分支默认 `main`，与下文脚本一致。）

### 2）环境与数据目录

```bash
cp .env.example .env
nano .env   # 至少设置 YMKY_SECRET_KEY；若用手机/浏览器通过局域网 IP 访问，建议配置 YMKY_TRUSTED_HOSTS（见 README）
mkdir -p data logs
```

### 3）先前台跑通（确认无误再上 systemd）

```bash
cd /home/wanhao/ymky_manager
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

另开终端测试：`curl -s http://127.0.0.1:8080/health`。确认后按 `Ctrl+C` 结束前台进程。

### 4）systemd 服务单元

创建 `/etc/systemd/system/ymky.service`：

```ini
[Unit]
Description=YMKY FastAPI Service
After=network.target

[Service]
Type=simple
User=wanhao
WorkingDirectory=/home/wanhao/ymky_manager
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/wanhao/ymky_manager/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ymky
sudo systemctl status ymky
```

### 5）允许部署脚本重启服务（无密码 sudo）

`scripts/server_git_pull_deploy.sh` 会执行 `sudo systemctl restart ymky`：

```bash
sudo visudo -f /etc/sudoers.d/ymky-deploy
```

写入（一行）：

```text
wanhao ALL=(root) NOPASSWD: /bin/systemctl restart ymky
```

---

## 自动更新：cron + server_git_pull_deploy.sh

脚本逻辑：`git pull` → 若 `requirements.txt` 变化则 `pip install` → `systemctl restart ymky`。

```bash
cd /home/wanhao/ymky_manager
chmod +x scripts/server_git_pull_deploy.sh
mkdir -p logs
./scripts/server_git_pull_deploy.sh
crontab -e
```

示例（每 5 分钟）：

```text
*/5 * * * * /home/wanhao/ymky_manager/scripts/server_git_pull_deploy.sh >> /home/wanhao/ymky_manager/logs/pull.log 2>&1
```

环境变量（可选）：`GIT_REMOTE=origin`、`DEPLOY_BRANCH=main`、`SERVICE_NAME=ymky`。

**HTTPS 克隆**时，服务器上 `git pull` 一般无需额外配置；**SSH 克隆**时，cron 非交互环境需保证已配置 **deploy key** 或 `ssh-agent`，否则 `git pull` 会失败。

---

## 本机日常（推送到 GitHub）

```powershell
git add -A
git commit -m "说明"
git push origin main
```

---

## 手动触发一次部署（不等 cron）

```powershell
ssh wanhao@<Ubuntu_IP> "cd /home/wanhao/ymky_manager && ./scripts/server_git_pull_deploy.sh"
```

或在 Windows 仓库根目录：

```powershell
.\scripts\deploy_via_git.ps1 -SshTarget wanhao@<Ubuntu_IP> -RemoteCd "/home/wanhao/ymky_manager"
```

---

## 附录：仍使用局域网 Windows 裸库时

若 `origin` 不是 GitHub 而是 `ssh://用户@内网IP/...` 的裸库，克隆 URL 以 `git remote get-url origin` 为准；其余步骤（venv、systemd、cron）相同。

---

## 注意事项

1. 勿将 `.env` 提交进 Git。
2. 勿用本机整目录覆盖服务器 `data/` 中的生产数据。
3. 若设置 `YMKY_TRUSTED_HOSTS`，需包含访问用主机名或 **局域网 IP（不含端口）**。

---

## 部署后自检

```bash
systemctl status ymky --no-pager
journalctl -u ymky -n 50 --no-pager
curl -s http://127.0.0.1:8080/health
```

浏览器：`http://<Ubuntu_IP>:8080`。
