# 云南云煤矿业开发有限公司 · 产销量管理系统

面向煤矿产销业务的内部 Web 平台：标准化填报、可追溯台账、统计可视化、报表导出与运维巡检。基于 **FastAPI + Jinja2**，支持 PC 与手机浏览器访问。

**代码仓库（主）：** [gitee.com/mvpwanhao/ykmymanager](https://gitee.com/mvpwanhao/ykmymanager)  
**当前版本：** 见根目录 [`VERSION`](./VERSION)（现为 **1.3.0**）；[`GET /health`](http://127.0.0.1:8080/health) 默认返回 `v` + 该号。完整变更见 [`CHANGELOG.md`](./CHANGELOG.md)。

---

## 版权与许可

**Copyright © 2026–2027 宛皓 (Wan Hao).**

本程序是自由软件：你可以再分发之和/或依照由自由软件基金会发布的 GNU Affero General Public License 之条款修改之，无论是许可证的第 3 版或是（按你的意见）任何以后版。

本程序为发布以期有用，但**不附有任何担保**；甚至不保证适销性或特定目的的适用性。详请参阅 GNU Affero General Public License。

你应已收到一份 GNU Affero General Public License 的副本。如果尚未收到，请访问 <https://www.gnu.org/licenses/>。

完整许可证文本见 [`LICENSE`](./LICENSE)。
---

## 功能概览

### 角色与权限

| 角色 | 主要能力 |
|------|----------|
| **管理员** | 数据可视化、历史台账（可编辑）、双通道填报、生成报表、密码管理、系统日志 |
| **填报人员** | 按登录时选择的口径填报「实际产量」或「能源局产销量」；查看本人历史记录 |
| **产量数据可视化** | 数据可视化、历史台账（只读） |

登录流程：选择身份 → 输入密码 →（填报人员）选择填报口径。管理员可在「密码管理」修改三类角色密码；运行时状态保存在 `data/runtime/`（不纳入 Git）。

### 业务功能

- **双通道填报**：实际产量 / 能源局口径产销量；同矿同日重复时支持「追加」或「覆盖」确认页
- **历史台账**：管理员可在线维护；可视化角色只读；按提交/报送时间倒序；各矿「今日是否已报」状态指示
- **数据可视化**：年度 / 月度 / 自定义区间；Plotly 饼图、柱状图、折线图；可导出含图表 PNG 的 Excel（`GET /export/visual-production.xlsx`）
- **报表生成**：实际产量统计（`sjcl1.xlsx` 模板）、能源局日报（`nybb.xlsx` 模板），输出至 `data/exports/`
- **微信通知**（可选）：填报成功后通过 Server酱（`SERVERCHAN_SENDKEY`）推送
- **运维**：`/health`、`/health/diag`（库连接、表行数、待同步标记）；管理员「系统日志」页查看 `data/ymky_system.log` 最近 500 行

### 数据存储

- **默认**：`data/*.xlsx` 台账 + 文件锁，适合单机与小规模部署
- **可选 PostgreSQL**：配置 `DATABASE_URL` 后读写数据库；连接失败时写入本地 Excel 缓冲，恢复后自动回同步库（顶栏黄色断线提示）
- **报表模板**（需存在于 `data/`）：`sjcl1.xlsx`（实际产量报表与日计划）、`nybb.xlsx`（能源局日报）；旧版 `sjcl.xlsx` 仍可在配置中引用

---

## 技术栈

| 层次 | 选型 |
|------|------|
| 运行时 | Python 3.10+（本地）；Docker 镜像基于 **3.12**（见 `Dockerfile`） |
| Web | FastAPI、Starlette、Jinja2、Session 中间件 |
| 数据 | pandas、openpyxl、SQLAlchemy、psycopg2（可选） |
| 图表 / 导出 | Plotly、Kaleido 0.2.x（容器内需足够 `shm` 与中文字体） |
| 部署 | 本机 `uvicorn`；生产可选 **systemd + venv** 或 **Docker Compose**；外网可选 SakuraFrp / Cloudflare Tunnel（Compose profile） |

---

## 目录结构

```text
app/              # 路由、配置、存储、报表、可视化、通知
templates/        # Jinja2 页面
static/           # CSS / JS / Plotly 主题
data/             # 台账、模板、导出、运行时与日志（业务 xlsx 默认不进 Git）
scripts/          # 本地开发、版本号、部署与迁移脚本
docs/             # 部署、Docker、内网穿透等说明
VERSION           # 语义化版本号（/health 默认来源）
CHANGELOG.md      # 发布变更记录
```

---

## 快速开始（本地）

**环境：** Python 3.10+，Windows / macOS / Linux 均可。

```powershell
cd <项目根目录>
python -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：至少设置 YMKY_SECRET_KEY（≥16 字符）
```

启动（推荐热重载）：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
# 或： .\scripts\dev.ps1
```

访问：

- 首页：`http://127.0.0.1:8080`（未登录会跳转 `/login`）
- 健康检查：`http://127.0.0.1:8080/health`
- 诊断：`http://127.0.0.1:8080/health/diag`

若 `8080` 已被占用（Windows 常见 `WinError 10048`），可改用 `--port 8081`，或确认是否已有实例在跑。

首次运行会在 `data/` 下创建台账空表与 `data/exports/`；请确保报表模板 `sjcl1.xlsx`、`nybb.xlsx` 已放在 `data/`（仓库可能仅含部分模板文件）。

自动化助手在本仓库的约定：[`AGENTS.md`](./AGENTS.md)。

---

## 环境变量

完整示例与注释见 [`.env.example`](./.env.example)。常用项：

| 变量 | 说明 |
|------|------|
| `YMKY_SECRET_KEY` | 会话 Cookie 签名密钥（**生产必填**强随机） |
| `YMKY_ENV` | `development`（默认）或 `production` |
| `YMKY_TRUSTED_HOSTS` | Host 白名单，逗号分隔、不含端口；手机经局域网 IP 访问须包含该 IP |
| `YMKY_APP_VERSION` | 可选，覆盖 `/health` 的 `version` |
| `YMKY_SESSION_TTL` | 会话秒数，默认 28800（8 小时） |
| `YMKY_LOCAL_DEBUG` | `1` 时开发环境登录页预填密码（**生产务必关闭**） |
| `YMKY_PASSWORD_*` | 三类角色初始密码；可被后台修改后的 `data/runtime/app_passwords.json` 覆盖 |
| `DATABASE_URL` | 可选，PostgreSQL 连接串 |
| `SERVERCHAN_SENDKEY` | 可选，Server酱推送 |
| `NATFRP_TOKEN` / `CLOUDFLARE_TUNNEL_TOKEN` | 仅 Docker Compose 穿透 profile 使用 |

密码还可从 `.streamlit/secrets.toml` 的 `[passwords]` 段读取（兼容旧项目习惯）。

---

## 部署方式

按场景三选一（勿在同一台机器上让 systemd 与 Docker 同时占用 `8080`）：

| 方式 | 适用 | 文档 / 脚本 |
|------|------|-------------|
| **直部署（推荐内网服务器）** | Ubuntu + venv + systemd，`git pull` 更新 | [`docs/DEPLOY_SYNC.md`](./docs/DEPLOY_SYNC.md)、`scripts/server_git_pull_deploy.sh` |
| **Docker Compose** | 小主机、需要隔离或与穿透同栈 | [`docs/DOCKER.md`](./docs/DOCKER.md)、`docker-compose.yml`、`scripts/server_git_pull_deploy_docker.sh` |
| **外网访问（可选）** | 无公网 IP 时 | SakuraFrp：[`docs/SAKURA_TUNNEL.md`](./docs/SAKURA_TUNNEL.md)（profile `natfrp`）；Cloudflare：[`docs/CLOUDFLARE_TUNNEL.md`](./docs/CLOUDFLARE_TUNNEL.md)（profile `cloudflared`） |

典型工作流（直部署）：

```text
本机：git commit → git push origin main（Gitee）
        ↓
服务器：git pull →（依赖变更时）pip install → systemctl restart ymky
```

Docker 局域网访问：`http://<宿主机IP>:8080`；`docker compose up -d --build` 前请配置 `.env` 并挂载 `./data`。

本机一键推送并触发远端 Docker 更新（需 SSH）：`scripts/deploy-push-remote-docker.bat` 或 `scripts/deploy_via_git.ps1`。

---

## 版本发布

```powershell
python scripts/bump_version.py patch   # 或 minor、major、--set x.y.z
```

随后更新 [`CHANGELOG.md`](./CHANGELOG.md)，与代码一并提交。向远端推送前请保持 `VERSION`、变更日志与本次改动一致。

---

## 运行巡检

**直部署（systemd）：**

```bash
systemctl status ymky --no-pager
journalctl -u ymky -n 100 --no-pager
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/health/diag
```

**Docker：**

```bash
docker compose ps
docker logs --tail 50 ymky-manager
curl -s http://127.0.0.1:8080/health
```

启用穿透时另查对应容器：`sakurafrp` 或 `cloudflared-tunnel`（见各文档）。

---

## 安全与运维

- **勿提交** `.env`、`data/runtime/`、真实台账 `actual_production.xlsx` / `energy_reporting.xlsx`、`natfrp/` 等（见 [`.gitignore`](./.gitignore)）
- 生产使用强随机 `YMKY_SECRET_KEY`，设置 `YMKY_ENV=production`，关闭 `YMKY_LOCAL_DEBUG`
- 经反向代理或域名访问时配置 `YMKY_TRUSTED_HOSTS`
- 定期备份 `data/`（或数据库）；穿透令牌泄露后须在对应控制台轮换并重建容器
- 生产环境只保留一种常驻进程（systemd **或** Docker），避免与手工 `nohup` 并行

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [`CHANGELOG.md`](./CHANGELOG.md) | 版本变更记录 |
| [`AGENTS.md`](./AGENTS.md) | Cursor / 自动化助手协作约定 |
| [`docs/DEPLOY_SYNC.md`](./docs/DEPLOY_SYNC.md) | Gitee 同步与 systemd 部署 |
| [`docs/DOCKER.md`](./docs/DOCKER.md) | Docker 构建、迁移、排障 |
| [`docs/SAKURA_TUNNEL.md`](./docs/SAKURA_TUNNEL.md) | SakuraFrp 内网穿透 |
| [`docs/CLOUDFLARE_TUNNEL.md`](./docs/CLOUDFLARE_TUNNEL.md) | Cloudflare Tunnel |

---

## 开发者自检

```powershell
python -m py_compile app/main.py app/storage.py app/report_engine.py app/services/notify.py
```

