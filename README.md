# 云煤产销量管理系统（FastAPI 版）

> **Copyright © 2026–2027 宛皓 (Wan Hao). All Rights Reserved.**
>
> 本软件著作权由宛皓完整持有。仅授予「云南云煤矿业开发有限公司」
> 及其关联方在内部业务系统中以非排他、不可转让的方式使用。
>
> **未经著作权人书面同意，禁止任何单位或个人对本软件实施：**
> 复制、反编译、转售、二次发行。
>
> 完整声明详见根目录 [`LICENSE`](./LICENSE) 文件。

在保留原业务（实际产量/能源局产销量填报、26 日制统计、模板报表、可选 PostgreSQL/Excel、Server酱 提醒）的基础上，用 **FastAPI + Jinja2** 重建，**响应式布局**，便于在 **PC 与手机浏览器** 使用。界面支持**浅色 / 深色 / 跟随系统**，偏好保存在浏览器 `localStorage`（键名 `ymky-theme`）。

> 原 Streamlit 项目仍保留在仓库根目录；新应用在子目录 `ymky_manager/`。

## 快速开始

```powershell
cd ymky_manager
python -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：设置 YMKY_SECRET_KEY、YMKY_PASSWORD_* 等
```

在 `data/` 中放入：

- `actual_production.xlsx`、`energy_reporting.xlsx`（可无，将自动创建），或
- 配置 `DATABASE_URL` 使用与旧版相同的两个表名。

从旧版迁移 Excel 时，可将老项目的表复制到 `data/`，或复用根目录的 `migrate_excel_to_db.py`（需设置 `DATABASE_URL`）。

**报表模板**（与旧版相同文件名）须放在 `data/`：

- `sjcl.xlsx`
- `nybb.xlsx`

启动：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

浏览器访问：`http://127.0.0.1:8080`  
健康检查：`http://127.0.0.1:8080/health`

## 配置说明

| 方式 | 说明 |
|------|------|
| `.env` | `YMKY_SECRET_KEY`、`DATABASE_URL`、`YMKY_PASSWORD_*` 等 |
| `../.streamlit/secrets.toml` | 若存在，可读 `[passwords]`（与旧项目兼容） |
| `data/runtime/app_passwords.json` | 管理员在「密码管理」中修改后的覆盖项 |

**PostgreSQL 与旧版统一**：`DATABASE_URL` 指向的库中，表名仍为 `actual_production`、`energy_reporting`；新写入行的列名、顺序与 Streamlit 老项目一致。若线上表多出一列 `提交时间`（能源局表），新程序不写该列，读入时仍保留老数据。补报用列 `年度总产量(吨)`（仅实际产量表、若有）会排在固定列后。

`产量数据可视化` 默认密码仍为 `ymky6666`（未单独配置时），请在首次登录后修改。

**部署上线前建议自检**

- `.env` 中设置强随机 `YMKY_SECRET_KEY`，并视情况将 `YMKY_ENV=production`（与默认开发密钥同时出现时会打日志提醒）。
- 经 Nginx/Caddy/Cloudflare 等反代、或使用域名访问时，设置 `YMKY_TRUSTED_HOSTS` 为允许的 `Host`（多个用英文逗号；Starlette 会按主机名匹配，**不含**端口，例如 `app.example.com,127.0.0.1`）。本机/内网临时调试可不设（留空即不启用校验）。
- 可选 `YMKY_APP_VERSION=版本号`：会出现在 `GET /health` 的 JSON 里，方便探活与发布核对。
- 生产环境**不要**打开 `YMKY_LOCAL_DEBUG`。
- 使用 `uvicorn` 时建议：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8080`（本机 + 由反代/隧道对公网），或直接由 systemd / NSSM 托管进程。

应用已包含：GZip（较大响应自动压缩）、静态资源长缓存（模板里 CSS/JS 带 `?v=` 指纹）、安全响应头（`X-Content-Type-Options` 等）、结构化启动日志。上线后可用 `GET /health` 确认 `ok: true` 与可选 `version`。

## 外网访问

参见 [docs/CLOUDFLARE_TUNNEL.md](docs/CLOUDFLARE_TUNNEL.md)。隧道指向 `http://127.0.0.1:8080` 即可。

Docker 部署（Ubuntu 小主机、`docker compose`、局域网访问）见 [docs/DOCKER.md](docs/DOCKER.md)。

本地调试通过后**同步到小主机（无 Docker）**：见 [docs/DEPLOY_SYNC.md](docs/DEPLOY_SYNC.md)（`git push` + 服务器 `git pull` + `systemctl restart ymky`）。

## 功能对照（相对旧版 Streamlit）

- 身份：管理员、填报人（两口径）、只读可视化  
- 实际产量/能源局填报、历史、管理台账、报表、改密  
- `?rt=` 书签恢复登录（与旧逻辑类似，基于文件内 token）  
- 拓展：历史记录 **导出 CSV**；界面为移动优先单栏 + 大触控区域  
- **重复填报检测**：提交「实际产量」或「能源局产销量」时，若该煤矿同一生产日期已有记录，
  会跳转到二次确认页（同时展示「已有记录」与「本次拟提交」两张表），可选「仍然追加」
  保留旧记录，或「覆盖」先删除该 矿+日期 的全部旧行后写入新行。Excel 与 PostgreSQL
  存储模式行为一致。

## 开发检查

```powershell
python -m py_compile app/main.py app/storage.py app/report_engine.py
```
