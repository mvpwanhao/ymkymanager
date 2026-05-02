# 云南云煤矿业开发有限公司 · 产销量管理系统

> 内部生产数据填报与经营报送平台  

## 当前版本与更新日志

- **默认版本号：** 仓库根目录 [`VERSION`](./VERSION)（仅 `MAJOR.MINOR.PATCH` 一行）；接口 [`GET /health`](http://127.0.0.1:8080/health) 返回的 **`version`** 字段默认为该号加 `v` 前缀（例：`VERSION`=`1.1.2` → **`v1.1.2`**）。
- **环境变量覆盖：** 若 `.env` 中设置了 **`YMKY_APP_VERSION`**，则 `/health` 始终返回该值（临时标注用）；常态化发版可留空，以仓库 `VERSION` 为准。
- **完整变更记录：** **[CHANGELOG.md](./CHANGELOG.md)**（推送前请务必更新）
- **递增版本：** `python scripts/bump_version.py patch`（或 `minor`、`major`、`--set x.y.z`），然后编辑 `CHANGELOG.md` 与该次改动一并提交。

---

## 版权与使用

**Copyright © 2026-2027 宛皓 (Wan Hao). All Rights Reserved.**

本软件著作权由宛皓完整持有。仅授权「云南云煤矿业开发有限公司」及其关联方在内部业务系统中非排他、不可转让地使用。未经著作权人书面许可，禁止复制、反编译、转售或二次发行。详见 `LICENSE`。

---

## 项目定位

本系统基于 `FastAPI + Jinja2` 构建，面向煤矿产销业务场景，聚焦“**标准化填报、可追溯台账、自动化报表、稳定上线运维**”四大能力，支持 PC 与移动端浏览器访问。

---

## 核心能力

- 多角色权限体系：管理员 / 填报人员 / 数据可视化角色
- 双通道填报流程：
  - 实际产量填报
  - 能源局口径产销量填报
- 同矿同日重复填报保护：支持“追加”与“覆盖”确认
- 历史记录查询与管理员台账在线维护
- 一键生成导出报表：
  - 实际产量统计报表（基于 `sjcl1.xlsx` 模板）
  - 能源局日报（基于 `nybb.xlsx` 模板）
- 微信通知（Server酱）：填报成功后可自动发送
- 健康检查接口：`/health`（支持输出版本号）

---

## 技术架构

- **Backend:** Python 3.10+, FastAPI, Starlette
- **Template/UI:** Jinja2 + 原生静态资源
- **Data Layer:** pandas, openpyxl
- **Storage Mode:** Excel（默认）/ PostgreSQL（可选）
- **Process:** systemd（生产常驻）
- **External Access:** SakuraFrp Docker 启动器（`docker-compose.yml` + `docs/SAKURA_TUNNEL.md`，替代原 Cloudflare Tunnel）

---

## 目录总览

- `app/`：业务主代码（路由、配置、存储、报表、通知）
- `templates/`：页面模板
- `static/`：前端静态资源
- `data/`：业务数据、报表模板、导出文件
- `scripts/`：部署与运维脚本
- `docs/`：部署、同步、容器、隧道等文档
- `CHANGELOG.md`：面向发布的更新日志（**向远端推送代码前须随提交更新**，见文件内约定与 `docs/DEPLOY_SYNC.md`）

---

## 快速启动（本地）

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
# 日常开发建议使用 --reload（改代码保存后进程自动重启）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
# 等价： .\scripts\dev.ps1
```

访问：

- `http://127.0.0.1:8080`
- `http://127.0.0.1:8080/health`

开发与自动化助手在本仓库的执行约定（热重载、何时部署等）：[`AGENTS.md`](./AGENTS.md)。

---

## 数据与模板

默认数据根目录为 `data/`：

- 实际产量台账：`actual_production.xlsx`
- 能源局台账：`energy_reporting.xlsx`
- 实际产量模板：`sjcl1.xlsx`
- 能源局模板：`nybb.xlsx`
- 导出目录：`data/exports/`

> 若配置 `DATABASE_URL`，系统将切换到 PostgreSQL；未配置时默认使用 Excel 文件存储。

---

## 环境变量（关键项）

- `YMKY_SECRET_KEY`：会话签名密钥（生产必配强随机）
- `YMKY_ENV`：`development` / `production`
- `YMKY_TRUSTED_HOSTS`：Host 白名单（逗号分隔，不含端口）
- `YMKY_APP_VERSION`：可选，覆盖 `/health` 的 `version`；不设时默认读仓库 [`VERSION`](./VERSION)（见文末「当前版本与更新日志」）
- `YMKY_SESSION_TTL`：会话有效期（秒）
- `YMKY_PASSWORD_ADMIN`
- `YMKY_PASSWORD_REPORTER`
- `YMKY_PASSWORD_VIEWER`
- `SERVERCHAN_SENDKEY`：微信通知（可选）
- `DATABASE_URL`：数据库连接（可选）

---

## 生产部署建议

推荐采用 **No-Docker + systemd + Git 同步**：

1. 本机提交并推送到 Gitee：`git push origin main`
2. 服务器执行拉取部署脚本：`scripts/server_git_pull_deploy.sh`
3. 自动按需安装依赖并重启 `ymky` 服务

完整文档：

- 部署同步：`docs/DEPLOY_SYNC.md`
- Docker 部署：`docs/DOCKER.md`
- SakuraFrp（外网穿透）：`docs/SAKURA_TUNNEL.md`
- Cloudflare Tunnel（历史）：`docs/CLOUDFLARE_TUNNEL.md`

---

## 运行与巡检

```bash
# 应用服务
systemctl status ymky --no-pager
journalctl -u ymky -n 100 --no-pager

# SakuraFrp 穿透（Docker）
docker compose --profile natfrp ps
docker logs --tail 50 sakurafrp

# 健康检查
curl -s http://127.0.0.1:8080/health
```

---

## 安全与运维建议

- 严禁提交 `.env`、密钥、数据库凭据
- 使用强随机 `YMKY_SECRET_KEY`
- 配置 `YMKY_TRUSTED_HOSTS` 防止 Host 头滥用
- 定期备份 `data/`（或数据库）
- SakuraNat `NATFRP_TOKEN` / 面板密码泄露后立即在面板重置与轮换 `.env`
- 生产环境仅保留 systemd 进程，不并行手工 `nohup` 进程

---

## 开发者检查

```powershell
python -m py_compile app/main.py app/storage.py app/report_engine.py app/services/notify.py
```
