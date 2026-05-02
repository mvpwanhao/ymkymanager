# 更新日志

本文档格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

**约定：** **`VERSION`**（仓库根单文件三段式）为本项目**默认对外版本号的唯一真源**；`/health` 返回的 `version` 取自该文件（前缀 `v`），除非设置了 **`YMKY_APP_VERSION`** 覆盖。**向远端推送前**须在 `CHANGELOG.md` 增补本次条目并与 `VERSION`/`commit` 说明一致。

## [Unreleased]

## [1.2.0] - 2026-05-02

### 新增

- 数据可视化：**导出当前统计区间 Excel 报表**（`GET /export/visual-production.xlsx`）：查询参数与页面「年度 / 月度 / 自定义」一致；工作表 **「日均产量」** 为各矿按日产量宽表、日合计与期间合计；工作表 **「图表」** 嵌入与页面同源的饼图、柱状图、折线图 **PNG** 快照（Plotly + Kaleido）。权限与数据可视化入口相同（管理员、产量数据可视化）。
- **`scripts/deploy-push-remote-docker.bat`**：`git push` 后 SSH 执行远端 **`scripts/server_git_pull_deploy_docker.sh`**（可选 `-nopush`）；配合 UTF-8 控制台与 BOM，减少中文乱码。

### 运维

- Docker Compose 可选服务 **`sakurafrp`**（启动器 **`natfrp.com/launcher`**、`container_name: sakurafrp`、`network_mode: host`、`profiles: natfrp`）；说明见 **`docs/SAKURA_TUNNEL.md`**；`.env.example` 增补 **`NATFRP_TOKEN`** / **`COMPOSE_PROFILES`**。
- **`docker-compose.yml`**：**`cloudflared`**（**`profiles: cloudflared`**）：仅向容器注入 **`TUNNEL_TOKEN`**（由项目根 `.env` 的 **`CLOUDFLARE_TUNNEL_TOKEN`** 插值），**不**挂载整份 `.env`，避免 JWT 出现在 `cloudflared` 启动日志。
- **`docs/CLOUDFLARE_TUNNEL.md`**：Ingress **`http://ymky:8080`**、**Error 1016** 排障、**换新隧道**、API 取 **`CLOUDFLARE_TUNNEL_TOKEN`** 等；**.env.example** 与 **README** / **DOCKER** 对齐说明。

### 变更

- **`requirements.txt`**：`kaleido`、`pillow`（图表静态导出与 openpyxl 插图）。
- **`Dockerfile`**：除 `gcc` 外增加 Kaleido/Chromium 常见运行时依赖（如 `libcairo2`、`libglib2.0-0`、`libnss3`、`fonts-liberation` 等），便于容器内生成 PNG。

### 修复

- 数据可视化：**日产量趋势** — 横轴使用完整日期而非仅 `月-日` 字符串，避免 Plotly 误解析；长区间（如「年度」）减少过密刻度与点位文字堆叠，并加大折线图下边距（`plotly-theme.js`）；**「年度」**折线横轴为有数据的首日至末有数据日（且不超过统计年末与**今天**北京时间）。

## [1.1.3] - 2026-04-30

### 新增

- 数据可视化「各矿产量占比」饼图：在图表区左上角以文字展示当前所选时间段内**实际总产量**（吨）。
- 实际产量、能源局产销量**提交后读回校验**：保存完成后按「煤矿 + 生产日期」在台账（PostgreSQL 或 Excel）中查找与本次**产量**（能源局另含**销量**）在 0.02 吨容差内一致的记录；找不到则提示勿以为已成功、请重试或联系管理员，并写 **ERROR** 级日志（路径、是否数据库模式等），且**不会**再发 Server 酱成功通知。

### 文档

- 根目录 **[`AGENTS.md`](./AGENTS.md)**：本地热重载与「仅明确说明后再 push/部署」等协作约定；**`README.md`** 推荐 `uvicorn --reload`；**`scripts/dev.ps1`** 一键启动带热重载的开发服务。
- **维护说明**：上条及本条《更新日志》中关于「开发与本地」「重复确认取消按钮」等条目，为 **2026-05-01** 对已随 v1.1.3 **一并上线**行为的 **追记**（与同日 `CHANGELOG` 仓库提交一致），不改变 `VERSION`。

### 修复

- 饼图总产量说明与扇区外侧标签重叠：缩小饼图 `domain`、加大边距、图例移至右侧留白区；明暗主题切换时仅覆盖 `legend.font.color`，保留 Python 中设置的图例位置。
- 饼图布局：`legend.itemwidth` 设为小于 Plotly 下限（30）会导致 `ValueError`，打开「数据可视化」首页报错 500——已改为合法最小值。
- 深浅色主题下图例默认白底：在 `plotly-theme.js` 中为图例设透明背景并与纸面同色区一致；饼图服务端布局同步 `legend.bgcolor`/边框为透明以便首帧一致。
- 移动端竖屏：「各矿产量占比」外侧标签易被 `.plot-wrap` 裁切——饼容器增加 `plot-pie`、窄屏 `overflow: visible` 与安全区内边距；服务端饼图放宽左边距、`automargin`，窄屏时将图例改至底部并扩大 `domain`，宽屏时用 WeakMap 基线复原布局。
- Web 桌面：重复填报确认页——补回 **`nav`**（与角色一致的侧栏）；**`templates/base.html`** 为 `<main>` 增加 **`{% block main_class %}`**，便于该页挂载 **`main--duplicate-confirm`** 并去掉宽屏 **`max-width:1180px`** 限制，`card--duplicate-confirm` 略增内边距；**「取消」** 与「仍然追加」同为 **`btn-secondary`**（此前取消为幽灵按钮）。

## [1.1.2] - 2026-04-30

### 变更

- 版本管理：**`VERSION`** 为默认源码；`/health` 的 `version` 默认 `v{VERSION}`，保留 `.env` 中 **`YMKY_APP_VERSION`** 覆盖能力。
- 新增 **`scripts/bump_version.py`**：递增 patch/minor/major 或 `--set`。

### 文档

- `README.md`：增加「当前版本与更新日志」入口，正文链向 [`CHANGELOG.md`](./CHANGELOG.md)（便于 Gitee 首页展示）。
- 《部署同步》中与发版流水线描述对齐。


## [1.1.1] - 2026-04-30

### 修复

- 数据可视化「年度 / 月度」：统计年、统计月下拉由 `form.submit()` 改为 `requestSubmit()`（无 API 时回退）。原生 `submit()` 不派发 `submit` 事件，会导致全局「载入中」遮罩与 `sessionStorage` 滚动恢复逻辑未触发。

## [1.1.0] - 2026-04-30

### 新增

- 全局「载入中」遮罩：同站链接跳转、表单提交、以及非 `/health` 的 `fetch` 数据请求时展示（短请求延迟约 140ms 再显示，减少闪烁）；可通过 `data-no-global-busy` 关闭。
- 与服务端连续多次检测失败后，弹出「与服务器的连接已断开」提示，提供「重新检测」触发 `/health`；无顶栏页面（如登录）同样进行后台探测。
- 脚本 `scripts/server_export_pg_to_excel.py`：在服务器上从 `.env` 的 `DATABASE_URL` 读取 PostgreSQL 台账并导出为 `data/*.xlsx`（子进程临时清空 `DATABASE_URL`，避免仅写库不写文件）。

### 变更

- 数据可视化：切换「年度 / 月度 / 自定义」及同卡片内相关 GET 表单提交后，用 `sessionStorage` 恢复滚动位置。
- 自定义统计区间：日期选择器与后端均限制不超过北京时间当天。
- 顶栏品牌：公司与「产销量管理系统」统一无衬线，以字重与字距区分层次。
- 全站页面背景与登录页一致（角部柔光 + 点阵 + 淡椭圆光），明暗主题分别适配。

## [1.0.0] - Birth

- 初始发行版（产销量管理系统 birth release），详见仓库 `README.md` 与 `LICENSE`。
