# 本地开发 → 直部署到服务器（无 Docker）

目标：在本机改代码、调试通过后，将提交推送到局域网 Git；服务器执行 `git pull` 并重启 systemd 上的 Python 进程，以应用变更。

> 适用：**不采用 Docker**，在 Ubuntu 上用 `venv` + `uvicorn` + `systemd` 运行。

---

## 推荐工作流

```text
本机：修改 / 调试 → git commit → git push 到局域网仓库
                          ↓
服务器：git pull（cron 或手动）→ 若依赖变更则 pip install → systemctl restart ymky
```

- 本机只做开发与提交。
- 服务器保留自己的 `.env` 与业务 `data/`，勿用本机整目录覆盖。

下文默认：服务器用户名 **wanhao**，项目目录 **`/home/wanhao/ymky_manager`**；局域网示例 IP：**192.168.14.222**。请按需替换。

---

## 服务器一次性准备

### 1）克隆仓库并创建虚拟环境

**URL 填什么：** 必须与「你在开发机上 `git push` 的目标远端」是**同一个仓库**，且 Ubuntu 从服务器能连通（一般用 SSH）。

在 Windows 开发机、工作副本目录执行 `git remote get-url origin`。若输出形如 `ssh://...` 或其它，部署机上 `git clone` 应指向**可被该服务器解析并认证**的同一裸库／中央库 URL（主机名、局域网 IP、`/path` 等与你的网络一致）。

**示例**（与本节文末「附录：Windows 裸库」一致：用户 `zJz`，宿主机 `192.168.14.132`，裸库 `D:\git-remotes\ymky_manager.git`；SSH 路径里盘符常写成 `/D/...`）：

```bash
git clone ssh://zJz@192.168.14.132/D/git-remotes/ymky_manager.git /home/wanhao/ymky_manager
cd /home/wanhao/ymky_manager
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

若你的真实 `origin` 与示例不同，只改 **`git clone` 那一行的 URL**，目标目录仍可保持 `/home/wanhao/ymky_manager`。

### 2）环境与数据目录

```bash
cp .env.example .env
nano .env   # 至少设置 YMKY_SECRET_KEY
mkdir -p data logs
```

### 3）systemd 服务单元

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

### 4）允许部署脚本重启服务（无密码 sudo）

`scripts/server_git_pull_deploy.sh` 会执行 `sudo systemctl restart ymky`。为该用户放行最小 sudo：

```bash
sudo visudo -f /etc/sudoers.d/ymky-deploy
```

写入（一行）：

```text
wanhao ALL=(root) NOPASSWD: /bin/systemctl restart ymky
```

---

## 自动更新：cron + server_git_pull_deploy.sh

仓库内脚本：`scripts/server_git_pull_deploy.sh`（pull → 若 `requirements.txt` 变化则 pip install → `systemctl restart ymky`）。

```bash
cd /home/wanhao/ymky_manager
chmod +x scripts/server_git_pull_deploy.sh
mkdir -p logs
./scripts/server_git_pull_deploy.sh   # 先手动跑一次确认无报错
crontab -e
```

示例（每 5 分钟执行一次）：

```text
*/5 * * * * /home/wanhao/ymky_manager/scripts/server_git_pull_deploy.sh >> /home/wanhao/ymky_manager/logs/pull.log 2>&1
```

若默认分支不是 `main`，在执行前设置环境变量，例如：`DEPLOY_BRANCH=master`。

若远程是 `git@...`，需保证 cron 在非交互环境下能完成认证（deploy key / ssh-agent / HTTPS token 等）。

---

## 本机日常

```powershell
git add -A
git commit -m "说明"
git push origin main
```

（远端名与分支以你仓库为准。）

推送后，服务器在下一轮 cron 会拉代码并重启服务。

---

## 手动触发一次部署（不等 cron）

### 方法一：SSH 一条命令

```powershell
ssh wanhao@192.168.14.222 "cd /home/wanhao/ymky_manager && ./scripts/server_git_pull_deploy.sh"
```

### 方法二：仓库内 PowerShell 脚本

```powershell
.\scripts\deploy_via_git.ps1 -SshTarget wanhao@192.168.14.222 -RemoteCd "/home/wanhao/ymky_manager"
```

若本机已 `git push` 完毕，可加 `-NoPush`。

---

## 附录：Windows 裸库 + 服务器 origin

若本机在 **Windows** 上建裸库（例如 `D:\git-remotes\ymky_manager.git`），局域网 IP **192.168.14.132**，用户 **zJz**，并已开启 OpenSSH Server，Ubuntu 上首次拉代码与上文「1）」**同一条命令**为宜，示例：

```bash
git clone ssh://zJz@192.168.14.132/D/git-remotes/ymky_manager.git /home/wanhao/ymky_manager
```

路径、用户、IP 以你实际为准；若克隆失败，在 Windows 侧确认裸库真实路径、`sshd_config`（如允许该用户访问该目录）以及从 Ubuntu `ssh zJz@192.168.14.132` 可登录后再试。

---

## 注意事项

1. 勿将含密钥的 `.env` 提交进 Git。
2. 勿将本机 `data/` 整目录覆盖服务器，以免覆盖生产数据。
3. `systemctl restart` 依赖前述 sudoers 或无密码 sudo 配置。
4. 若配置 `YMKY_TRUSTED_HOSTS`，需包含浏览器访问使用的主机名或 IP（不含端口）。

---

## 部署后自检

在服务器：

```bash
systemctl status ymky --no-pager
journalctl -u ymky -n 100 --no-pager
curl -s http://127.0.0.1:8080/health
```

局域网浏览器访问：`http://192.168.14.222:8080`（IP 与端口按实际）。
