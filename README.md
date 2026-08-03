# 云南云煤矿业开发有限公司 · 产销量管理系统

> 面向煤矿产销业务的轻量级 Web 平台。支持双通道填报、可追溯台账、统计可视化、报表导出与运维巡检，专为云南云煤矿业内部业务场景设计。

仓库：[gitee.com/mvpwanhao/ykmymanager](https://gitee.com/mvpwanhao/ykmymanager)  
当前版本：**1.5.0**（见 VERSION，/health 默认返回 v + 该号）  
变更记录：CHANGELOG.md

---

## 版权与许可

**Copyright © 2026–2027 宛皓 (Wan Hao).**

本程序依 GNU Affero General Public License v3 发布，不附任何担保。完整许可文本见 LICENSE。

---

## 功能概览

### 角色与权限

| 角色 | 主要能力 |
|------|----------|
| **管理员** | 数据可视化、历史台账（可编辑）、双通道填报、生成报表、密码管理、系统日志 |
| **填报人员** | 按登录时选择的口径填报「实际产量」或「能源局产销量」；查看本人历史记录 |
| **产量数据可视化** | 数据可视化、历史台账（只读） |

### 业务功能

- **双通道填报**：实际产量 / 能源局口径产销量；同矿同日重复时支持「追加」或「覆盖」确认页
- **实际销量填报**：按周填报各矿实际销量；不选煤矿时可单独更新年累计掺配煤/外购煤；重复填报可选择追加或覆盖
- **历史台账**：管理员可在线编辑；可视化角色只读；按提交/报送时间倒序；各矿「今日是否已报」状态指示；列宽可拖拽调整
- **数据可视化**：年度 / 月度 / 自定义区间；ECharts 客户端渲染（饼图、柱状图、折线图）；KPI 概览 + 矿明细表 + Excel 导出
- **报表生成**：实际产量统计（sjcl1.xlsx）、能源局日报（nybb.xlsx）、周报表及产销量简报（weeksheet.xlsx，吨表+万吨表，支持自定义日期区间，一键同时生成 Excel 和文本简报）
- **微信告警**（可选）：服务异常时通过 Server酱推送（仅在 5xx 错误、未处理异常、健康检查失败时触发）
- **运维工具**：/health、/health/diag（库连接、表行数、待同步标记）；管理员「系统日志」页查看最近 500 行日志

### 数据存储

- **默认**：data/*.xlsx 台账 + 文件锁，适合单机与小规模部署
- **可选 PostgreSQL**：配置 DATABASE_URL 后读写数据库；连接失败时写入本地 Excel 缓冲，恢复后自动回同步库（顶栏黄色断线提示）
- **报表模板**：sjcl1.xlsx（实际产量报表与日计划）、nybb.xlsx（能源局日报）、weeksheet.xlsx（周报表，吨表+万吨表）——需存在于 data/ 目录

---

## 前端设计体系（Material Design 3）

自 **1.5.0** 起，整套界面基于 **Material Design 3** 设计语言重写，与品牌视觉统一、明暗双主题自适应。

- **设计令牌**：以品牌蓝 `#0062A8` 为源色经 MD3 tonal 算法生成完整系统色角色（primary / secondary / tertiary / error，另补 success / warning 语义色），并构建明 / 暗双 scheme 与多级 `surface-container` 层级；旧 `--c-*` 变量全部以别名映射保留，向后兼容既有组件。
- **组件规范**：按钮采用 stadium 全圆角（filled / tonal / outlined / text 四级，hover·active 用 state layer 叠加）；卡片、弹窗、载入面板分别使用 16px / 28px 圆角；分段控件（pill-tabs）、筛选 chip（选中自动带 ✓）、导航抽屉（选中项 secondary-container 全圆角 pill）、通知条（tonal 无边框容器）均遵循 MD3 形态。
- **表单与细节**：输入框为 MD3 outlined 样式（16px 字号避免移动端聚焦缩放，聚焦态主色描边光晕）；原生控件 `accent-color` 统一为主色；滚动条、文字选区、下拉选项弹层均按主题令牌着色（已修复 Windows 原生 `<select>` 在深色模式下「白底白字」问题）。
- **可视化**：ECharts 配色切换为 MD3 tonal 调色板（明 / 暗两套随主题自动切换），图表背景透明以融入 tonal 图表面板。
- **质感**：移除玻璃拟态与角部光晕 / 点阵纹理，改为 MD3 扁平 tonal surface；移动端浏览器 `theme-color` 跟随页面底色。

---

## 技术栈

| 层次 | 选型 | 版本 |
|------|------|------|
| 运行时 | Python | ≥ 3.10（本地）；Docker 基于 3.12-slim-bookworm |
| Web 框架 | FastAPI + Starlette | ≥ 0.110.0 |
| 模板引擎 | Jinja2 | ≥ 3.1.0 |
| 会话管理 | itsdangerous | ≥ 2.1.0 |
| 数据处理 | pandas + openpyxl | ≥ 2.0.0 / ≥ 3.1.0 |
| 可视化 | ECharts（客户端渲染） | ≥ 5.4.0 |
| ORM（可选） | SQLAlchemy + psycopg2 | ≥ 2.0.0 / ≥ 2.9.0 |
| HTTP 服务器 | Uvicorn | ≥ 0.27.0 |
| 部署 | Docker Compose / systemd + venv | - |

---

## 目录结构

```text
ymky_manager/
├── app/                        # FastAPI 应用主体
│   ├── main.py                 #    路由注册、生命周期、中间件（115 行）
│   ├── config.py               #    环境变量解析 (Pydantic Settings)
│   ├── storage.py              #    Excel/PostgreSQL 双存储引擎
│   ├── report_engine.py        #    报表生成（实际产量/能源局日报/周报表/简报）
│   ├── viz_engine.py           #    可视化统计引擎（ECharts 数据聚合）
│   ├── helpers.py              #    共享辅助函数
│   ├── utils.py                #    工具函数（exclude_mines 等）
│   ├── constants.py            #    矿区、角色等常量
│   ├── timeutil.py             #    时间工具（26 日制、周区间计算）
│   ├── release_version.py      #    版本号读取
│   ├── routes/                 #    路由模块（health/auth/entry/report/viz/admin/pages）
│   ├── auth/                   #    身份验证与会话管理
│   └── services/
│       └── notify.py           #    Server酱异常告警推送
├── templates/                  # Jinja2 页面模板 (17 个)
├── static/                     # CSS / JS / logo
├── data/                       # 台账 Excel、模板、导出、运行时与日志
├── scripts/                    # 开发、发版、部署、迁移脚本
├── tests/                      # 单元测试（pytest，46 个）
├── docs/                       # 部署、Docker、内网穿透说明
├── docker/                     # Docker 构建配置 (fontconfig)
├── docker-compose.yml          # 多容器编排（含穿透 profile）
├── Dockerfile                  # 生产镜像定义
├── requirements.txt            # Python 依赖
├── requirements-dev.txt        # 开发依赖（pytest 等）
├── .env.example                # 环境变量示例
├── VERSION                     # 语义化版本号
├── CHANGELOG.md                # 发布变更记录
└── agent.md                    # AI 助手运维手册（内部）
```

---

## 环境搭建与运行

### 前置条件

- Python ≥ 3.10
- 确保 data/ 下已放入报表模板 sjcl1.xlsx 和 nybb.xlsx

### 1. 安装依赖

```powershell
cd ymky_manager
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

```powershell
copy .env.example .env
# 编辑 .env，至少设置 YMKY_SECRET_KEY（≥16 字符强随机值）
```

**常用环境变量：**

| 变量 | 说明 | 必填 |
|------|------|:---:|
| YMKY_SECRET_KEY | 会话 Cookie 签名密钥，生产环境务必设置强随机值 | ✓ |
| YMKY_ENV | development（默认）或 production | - |
| YMKY_TRUSTED_HOSTS | Host 白名单，逗号分隔且不含端口 | - |
| YMKY_APP_VERSION | 可选，覆盖 /health 返回的版本号 | - |
| YMKY_SESSION_TTL | 会话超时秒数，默认 28800（8 小时） | - |
| YMKY_LOCAL_DEBUG | 1 时登录页预填密码（生产务必关闭） | - |
| YMKY_PASSWORD_* | 三类角色初始密码，可被后台修改后的 runtime 文件覆盖 | - |
| DATABASE_URL | 可选，PostgreSQL 连接串 | - |
| SERVERCHAN_SENDKEY | 可选，Server酱异常告警推送 | - |

密码也可从 .streamlit/secrets.toml 的 [passwords] 段读取。

### 3. 本地启动

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

访问：
- 首页：http://127.0.0.1:8080
- 健康检查：http://127.0.0.1:8080/health
- 诊断：http://127.0.0.1:8080/health/diag

若 8080 被占用，可改用 --port 8081。

---

## 生产部署

### 方案一：systemd + venv（推荐内网服务器）

参考 docs/DEPLOY_SYNC.md，核心流程：

```text
本机：git commit → git push origin main (Gitee)
              ↓
服务器：git pull →（依赖变更时）pip install → systemctl restart ymky
```

一键推送并触发远端更新：`scripts/deploy_via_git.ps1`

### 方案二：Docker Compose

```bash
# 在服务器上，首次或依赖变更时：
docker compose up -d --build

# 日常更新：
git pull && docker compose up -d --build

# 查看状态：
docker compose ps
docker logs --tail 50 ymky-manager
```

### 方案三：外网访问（可选）

无公网 IP 时，可配合穿透 profile：

| 方式 | 文档 | Compose Profile |
|------|------|------|
| SakuraFrp | docs/SAKURA_TUNNEL.md | natfrp |
| Cloudflare Tunnel | docs/CLOUDFLARE_TUNNEL.md | cloudflared |

---

## 发版流程

```powershell
python scripts/bump_version.py patch   # 或 minor / major / --set x.y.z
# 更新 CHANGELOG.md 后一并提交
```

---

## 运维与注意事项

### 日常巡检

**systemd 部署：**
```bash
systemctl status ymky --no-pager
journalctl -u ymky -n 100 --no-pager
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/health/diag
```

**Docker 部署：**
```bash
docker compose ps
docker logs --tail 50 ymky-manager
curl -s http://127.0.0.1:8080/health
```

### 微信告警规则

配置 SERVERCHAN_SENDKEY 后，系统**仅在以下异常场景触发推送**：

- HTTP 5xx 服务器错误（含请求路径、状态码、客户端信息）
- 未处理异常（含完整调用栈）
- 健康检查失败（配合 `scripts/health_check_alert.sh` 通过 cron 定时执行，建议每 5 分钟）

正常填报操作**不会**触发通知。每条告警包含错误类型、发生时间，异常场景附带调用栈，不泄露业务数据。

### 安全红线

- 勿提交 .env、data/runtime/、真实台账文件、natfrp/ 等（已配 .gitignore）
- 生产环境必须 YMKY_ENV=production 且 YMKY_LOCAL_DEBUG 关闭
- 经反向代理或域名访问时配置 YMKY_TRUSTED_HOSTS
- 同一机器只保留一种常驻进程（systemd 或 Docker），避免端口冲突
- 定期备份 data/ 目录或数据库

### 日志位置

| 日志 | 路径 |
|------|------|
| 应用日志 | data/ymky_system.log |
| 健康检查日志 | logs/health.log |
| systemd 日志 | journalctl -u ymky |
| Docker 日志 | docker logs ymky-manager |

---

## 相关文档

| 文档 | 内容 |
|------|------|
| CHANGELOG.md | 版本变更记录 |
| docs/DEPLOY_SYNC.md | systemd 直部署详解 |
| docs/DOCKER.md | Docker 构建、迁移、排障 |
| docs/SAKURA_TUNNEL.md | SakuraFrp 内网穿透 |
| docs/CLOUDFLARE_TUNNEL.md | Cloudflare Tunnel |
