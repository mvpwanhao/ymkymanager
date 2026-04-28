# 云煤产销量管理系统

> **Copyright © 2026–2027 宛皓 (Wan Hao). All Rights Reserved.**  
> 本软件著作权由宛皓完整持有。仅授予「云南云煤矿业开发有限公司」及其关联方在内部业务系统中以非排他、不可转让的方式使用。  
> 未经著作权人书面同意，禁止复制、反编译、转售、二次发行。详见 [`LICENSE`](./LICENSE)。

基于 **FastAPI + Jinja2** 的煤矿产销量管理系统，支持多角色登录、数据填报、台账管理、可视化与报表导出，适配 PC 与手机浏览器。

## 主要功能

- 角色权限：管理员、填报人员、产量数据可视化
- 数据填报：
  - 实际产量填报
  - 能源局口径产销量填报
- 重复填报检测：同矿同日期支持“追加”或“覆盖”
- 历史记录与管理员台账编辑
- 报表生成与下载：
  - 实际产量统计表（含备注写入 J 列）
  - 能源局日报
- 健康检查：`/health`

## 技术栈

- Python 3.10+
- FastAPI / Starlette
- Jinja2
- pandas / openpyxl
- 可选 PostgreSQL（默认支持 Excel 文件存储）

## 目录结构（核心）

- `app/`：后端业务代码
- `templates/`：页面模板
- `static/`：前端静态资源
- `data/`：数据文件、模板与导出目录
- `scripts/`：部署与运维脚本
- `docs/`：部署/隧道/容器说明

## 快速开始（本地）

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
```

编辑 `.env`（至少设置以下项）：

- `YMKY_SECRET_KEY`（必须，建议随机强密钥）
- `YMKY_PASSWORD_ADMIN`
- `YMKY_PASSWORD_REPORTER`
- `YMKY_PASSWORD_VIEWER`

启动：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

访问：

- 首页：`http://127.0.0.1:8080`
- 健康检查：`http://127.0.0.1:8080/health`

## 数据与模板说明

默认数据目录：`data/`

- 实际产量数据：`actual_production.xlsx`
- 能源局数据：`energy_reporting.xlsx`
- 报表模板：
  - `sjcl.xlsx`
  - `nybb.xlsx`
- 导出目录：`data/exports/`

如配置 `DATABASE_URL`，系统改为使用 PostgreSQL；未配置时使用 Excel 文件。

## 关键配置项（.env）

- `YMKY_SECRET_KEY`：会话签名密钥
- `YMKY_ENV`：`development` / `production`
- `YMKY_TRUSTED_HOSTS`：Host 白名单（逗号分隔，**不含端口**）
- `YMKY_APP_VERSION`：健康检查可选版本字段
- `YMKY_SESSION_TTL`：会话有效期（秒）
- `YMKY_LOCAL_DEBUG`：本地调试预填密码开关（生产建议关闭）
- `YMKY_PASSWORD_ADMIN` / `YMKY_PASSWORD_REPORTER` / `YMKY_PASSWORD_VIEWER`
- `DATABASE_URL`（可选）
- `SERVERCHAN_SENDKEY`（可选）

## 生产部署

### 无 Docker（推荐）

参考：[`docs/DEPLOY_SYNC.md`](docs/DEPLOY_SYNC.md)

当前默认代码远端：Gitee  
`origin = https://gitee.com/mvpwanhao/ykmymanager.git`

常规发布流程：

1. 本机 `git push origin main`
2. 服务器 `git pull origin main`
3. `sudo systemctl restart ymky`

### Docker 部署

参考：[`docs/DOCKER.md`](docs/DOCKER.md)

### 无公网 IP 外网访问

参考：[`docs/CLOUDFLARE_TUNNEL.md`](docs/CLOUDFLARE_TUNNEL.md)

## 运维常用命令

```bash
# 服务状态
systemctl status ymky --no-pager

# 最近日志
journalctl -u ymky -n 100 --no-pager

# 健康检查
curl -s http://127.0.0.1:8080/health
```

## 安全建议

- 生产环境使用强随机 `YMKY_SECRET_KEY`
- 不要将 `.env` 提交到仓库
- 配置 `YMKY_TRUSTED_HOSTS` 防止异常 Host 请求
- 定期备份 `data/` 或数据库

## 开发检查

```powershell
python -m py_compile app/main.py app/storage.py app/report_engine.py
```
