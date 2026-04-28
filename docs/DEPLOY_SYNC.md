# 本地开发 → 直部署到服务器（无 Docker）

目标：本机 **`git push` 到 [Gitee](https://gitee.com/mvpwanhao/ykmymanager)**（默认 `origin`）；Ubuntu 服务器从同一仓库 `clone` / `pull` 后以 `venv` + `uvicorn` + `systemd` 常驻运行。**GitHub** 仅作可选镜像（远端名 `github`）。

> **主仓库：** [gitee.com/mvpwanhao/ykmymanager](https://gitee.com/mvpwanhao/ykmymanager)  
> 适用：**不采用 Docker**，在 Ubuntu 上直接运行 Python。

---

## 推荐工作流

```text
本机：git commit → git push origin main（Gitee）
                          ↓
服务器：git pull（cron 或手动）→ 若依赖变更则 pip install → systemctl restart ymky
```

- 如需同时备份到 GitHub：`git push github main`（已为常见配置保留 `github` 远端）。
- 服务器长期保留各自的 `.env` 与真实 `data/`，勿被本机整目录覆盖。
- 下文默认用户名 **wanhao**，目录 **`/home/wanhao/ymky_manager`**。

---

## 服务器一次性准备

### 0）系统依赖（Ubuntu）

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv
```

防火墙若开启，按需：`sudo ufw allow 8080/tcp`。

### 1）从 Gitee 克隆并创建虚拟环境

**推荐使用 HTTPS（公开仓库可读）：**

```bash
git clone https://gitee.com/mvpwanhao/ykmymanager.git /home/wanhao/ymky_manager
cd /home/wanhao/ymky_manager
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

**若使用 Gitee SSH（已配置密钥）：**

```bash
git clone git@gitee.com:mvpwanhao/ykmymanager.git /home/wanhao/ymky_manager
```

**备选：仅从 GitHub 拉取**

若必须使用 GitHub：`https://github.com/mvpwanhao/ymkymanager.git`，或在中国大陆网络不稳定时可先试公益加速（不保长期）：`https://mirror.ghproxy.com/https://github.com/mvpwanhao/ymkymanager.git`。建议优先仍用 **本仓库 Gitee 地址**，内地访问最省事。

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

另开终端：`curl -s http://127.0.0.1:8080/health`。确认后按 `Ctrl+C` 停止。

### 4）systemd 服务单元

`/etc/systemd/system/ymky.service`：

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

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ymky
sudo systemctl status ymky
```

### 5）允许部署脚本重启服务（无密码 sudo）

```bash
sudo visudo -f /etc/sudoers.d/ymky-deploy
```

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

```text
*/5 * * * * /home/wanhao/ymky_manager/scripts/server_git_pull_deploy.sh >> /home/wanhao/ymky_manager/logs/pull.log 2>&1
```

环境变量（可选）：`GIT_REMOTE=origin`、`DEPLOY_BRANCH=main`。`origin` 指向 Gitee 时，在内地一般无需额外代理。

---

## 本机日常

```powershell
git add -A
git commit -m "说明"
git push origin main
```

若要同步镜像到 GitHub：`git push github main`。

---

## 手动触发部署

```powershell
ssh wanhao@<Ubuntu_IP> "cd /home/wanhao/ymky_manager && ./scripts/server_git_pull_deploy.sh"
```

或：

```powershell
.\scripts/deploy_via_git.ps1 -SshTarget wanhao@<Ubuntu_IP> -RemoteCd "/home/wanhao/ymky_manager"
```

---

## 附录：局域网 Windows 裸库

裸库地址以 `git remote get-url origin` 为准。

---

## 注意事项

1. 勿提交 `.env`。
2. 勿用本机覆盖服务器生产 `data/`。
3. `YMKY_TRUSTED_HOSTS` 需含浏览器访问时使用的主机名或局域网 IP（不含端口）。

---

## 部署后自检

```bash
systemctl status ymky --no-pager
journalctl -u ymky -n 50 --no-pager
curl -s http://127.0.0.1:8080/health
```

浏览器：`http://<Ubuntu_IP>:8080`。
