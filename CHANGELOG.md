# 更新日志

本文档格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

**约定：** **`VERSION`**（仓库根单文件三段式）为本项目**默认对外版本号的唯一真源**；`/health` 返回的 `version` 取自该文件（前缀 `v`），除非设置了 **`YMKY_APP_VERSION`** 覆盖。**向远端推送前**须在 `CHANGELOG.md` 增补本次条目并与 `VERSION`/`commit` 说明一致。

## [1.4.4] - 2026-07-17

### 优化

- **清理前端开发痕迹**：移除面向用户的技术实现细节文字
  - 数据可视化页面：移除统计口径内部实现说明（G/H 列引用、存储基数+后续F、I/J 回退取值、K=H+I 等）
  - 实际产量填报页面：移除开发占位符 `***`
  - 实际销量填报页面：移除"（最终以系统计算为准）"开发者免责提示
  - 历史记录页面：简化文件格式提示
  - 数据可视化加载/导出失败提示：不再向用户暴露原始错误信息

## [1.4.3] - 2026-07-17

### 工程

- **P0-1 清理 Plotly/Kaleido 死代码**：删除 `app/dashboard_data.py`、`app/visual_export.py`、`static/plotly-theme.js`；将 `exclude_mines` 和 `content_disposition_attachment` 迁移到新建 `app/utils.py`。
- **P0-2 瘦身依赖**：`requirements.txt` 移除 `plotly`、`kaleido`、`pillow`；Dockerfile 删除 kaleido 相关系统依赖（GTK3/NSS/fontconfig 等），预计减少镜像约 500 MB。
- **P0-3 Dockerfile 修复**：补全 `COPY scripts ./scripts`；`db_backup.sh` 硬编码端口 `-p 6543` 改为从 `DATABASE_URL` 动态解析。
- **P1-4 单元测试**：新建 `tests/` 目录，含 `conftest.py`、`test_timeutil.py`、`test_utils.py`、`test_viz_engine.py`、`test_storage.py`，46 个测试全部通过；新增 `requirements-dev.txt`。
- **P1-5 拆分 main.py**：1,420 行精简到 115 行 + 7 个路由模块（`app/routes/health.py`、`auth.py`、`entry.py`、`report.py`、`viz.py`、`admin.py`、`pages.py`），共享函数提取到 `app/helpers.py`。
- **P1-6 异常处理 + 登录限流**：`storage.py` 8 处 `except Exception` 添加 `exc_info=True` 记录完整 traceback；`auth.py` 新增登录限流（5 次/60 秒）。
- **P2-7 清理临时文件**：删除 13+ 个临时调试文件和 8 个论文相关废弃脚本。
- **P2-8 _PENDING_SYNC 持久化**：将内存标记 `_PENDING_SYNC` 持久化到 `data/runtime/pending_sync.flag` 文件，容器重启后自动恢复状态并触发 DB 同步，避免数据丢失。
- **P2-9 备份验证机制**：`db_backup.sh` 新增三步备份验证（文件大小、gzip 完整性、SQL 表名检查）；新建 `scripts/db_verify_backup.sh` 独立验证脚本。

## [1.4.2] - 2026-07-17

### 优化

- **数据可视化动态标签**：图表中的"期间产量/销量"根据所选区间自动变化
  - 选「年度」→ 显示"年度产量"、"年度销量"
  - 选「月度」→ 显示"7月产量"、"7月销量"（按所选月份）
  - 选「自定义」→ 保持"期间产量"、"期间销量"
- 涉及 KPI 卡片标签、各矿产量对比柱状图图例/系列名、产量占比饼图标题、明细表表头、Excel 导出表头
- 重构 Excel 导出表头映射逻辑（消除脆弱的字符串 replace 链）
- **图表过滤零数据煤矿**：柱状图和占比图中，所选区间内所有指标均为零的煤矿不再显示
- **柱状图显示数值标签**：产量/销量柱状图每个柱块顶部显示对应数值

## [1.4.1] - 2026-07-17

### 修复

- **数据可视化模块 HTTP 500**：`app/viz_engine.py` 中 `energy_yest_prod`/`energy_yest_sales` 字典的键是普通 Python 字符串，但错误地使用了 `str.startswith(prefix, na=False)`。`na=False` 是 pandas `Series.str.startswith()` 的参数，Python 原生 `str.startswith()` 不接受该参数，导致调用 `build_viz_data()` 时抛出 `TypeError`。已改为 `mine_key.startswith(prefix)`。

## [1.4.0] - 2026-07-17

### 新增

- **实际销量台账模块（周频填报）**：管理员可按周填报各矿实际销量，数据模型 11 列（填报时间、煤矿、周区间、销量、月/年累计自产煤销量、年累计掺配煤/外购煤、填报人、备注）；提交时按「煤矿 + 周区间」查重，重复填报可选择追加或覆盖。
  - `app/storage.py`：新增 `actual_sales` 表支持（`FILE_TABLE_MAP`、`ACTUAL_SALES_WRITE_ORDER`、`dataframe_actual_sales_new_row`、`find_sales_records_by_mine_week`、`replace_sales_records_for_mine_week` 等）。
  - `app/config.py`：新增 `actual_sales_path` 和 `weeksheet_template` 属性。
  - `app/timeutil.py`：新增 `get_weekly_range` / `enumerate_weekly_ranges` 周区间计算函数（26 日制统计月内：首周从 26 日起到首个周五，中间各周周六至周五，末周到 25 日）。
  - `templates/entry_sales.html`：销量填报页面。
  - `templates/_icons.html`：新增 `entry_sales` 图标。
  - `templates/admin_ledger.html`：新增「实际销量」Tab，支持在线编辑销量台账。
- **周报表生成**（`POST /reports/weekly`）：按周区间汇总各矿原煤生产量与自产煤销售量，生成吨表和万吨表两个 Sheet；复用 `weeksheet.xlsx` 模板。
- **产销量简报**（`POST /reports/brief`）：生成文本格式简报，可直接复制粘贴到微信群；含日产量、月/年累计、掺配煤/外购煤年累计、合计销售煤量（K=H+I）。
- **产销量数据可视化模块**（ECharts 客户端渲染）：
  - `app/viz_engine.py`：可视化统计引擎，完整复用报表/简报统计逻辑（G/H 混合累计、I/J 合计记录回退、K=H+I）。
  - `templates/dashboard.html`：重写为 ECharts 渲染，合并旧 Plotly 可视化与新 ECharts 分析模块。
  - 年度 / 月度 / 自定义三种时间段 AJAX 切换（无需页面刷新），统计结果与报表/简报完全对齐。
  - 9 个 KPI 卡片（期间产量/销量、月/年累计自产煤、掺配煤/外购煤年累计、K 值、今日报能源局产量/销量）。
  - 10 列矿明细表（含能源局产量/销量列）。
  - 6 个图表：各矿产量/销量对比柱状图、产量/销量占比饼图、日产量/周销量趋势折线图。
  - Tooltip 明暗主题自动适配；趋势折线图支持勾选显示合计与各矿数据线。
  - Excel 导出（3 个 Sheet：各矿产销量明细、日产量明细、周销量明细）。
- **销量数据导入脚本** `scripts/import_sales_to_db.py`：将本地 `actual_sales.xlsx` 导入部署环境 PostgreSQL；支持 `replace`（整表覆写）和 `upsert`（按煤矿+周区间去重合并）两种模式，`--dry-run` 预览；脚本不含业务数据，可安全纳入版本控制。

### 修复

- **简报年累计掺配煤/外购煤显示为 0**：按精确周结束日期匹配「合计」记录时，目标周无数据导致取不到值。新增 `effective_week_end` 回退逻辑——目标周无数据时取最近一期 `周结束日期 ≤ 目标周末` 的记录。
- **G/H 时间累计丢失补录历史数据**：纯时间累计（求和 F）在补录数据 F=0 时导致 G/H 累计值丢失。改为混合逻辑：以补录存储的 G/H 为基数，加上该基数记录之后的新增 F 值；无存储值时按时间累计。

### 变更

- **I/J 填报保持逻辑**：年累计掺配煤（I）/外购煤（J）填 0 或留空时，自动沿用最近一期「合计」记录的值（保持不变）；非 0 时覆盖。每次提交销量数据后自动同步更新/创建当前周的「合计」记录（含 I/J 值），使用 `FileLock` 确保读写原子性。
- **数据可视化合并**：删除旧 `templates/visualization.html`，统一以 `dashboard.html` 为入口；`app/main.py` 移除 `build_summary_and_charts` / `try_visual_export_bytes` 等旧 Plotly 导入。

### 工程与部署

- **`.gitignore` 修复**：新增 `data/actual_sales.xlsx` 排除规则（原先只排除了 `actual_production.xlsx` 和 `energy_reporting.xlsx`，存在业务数据误推送风险）。
- **`data/weeksheet.xlsx`**：新增周报表模板（吨表+万吨表两个 Sheet），作为项目组成部分纳入版本控制。

## [1.3.1] - 2026-06-09

### 新增

- **历史台账按煤矿筛选**：管理员和只读用户可在历史台账页面通过复选框多选煤矿名称进行筛选，选中后标签高亮显示；切换「实际产量」/「能源局产销量」Tab 时筛选项保持；PC 与移动端统一采用 Chip 标签样式。

### 修复

- **筛选状态下保存不再丢失数据**：修复了在筛选视图下点击「保存修改」会覆盖整个 Excel 文件、仅保留可见行的问题。现在通过每行携带 `orig_idx` 追踪原始位置，保存时仅更新有变更的行，未在表单中出现的行保持不变。

### 变更

- **Server酱推送改为仅异常告警**：移除填报成功通知逻辑，`notify_startup` 函数已删除，`notify_alert` 仅在 HTTP 5xx 错误和未处理异常时触发推送。每次告警含错误类型、时间戳和调用栈，不泄露业务数据。

### 文档与工程

- **README.md 全面重写**：新增技术栈版本表、目录树状图、环境变量必填标记、微信告警规则说明、日志位置表、三种部署方案分场景描述。
- **敏感信息清理**：agent.md（含服务器 IP、SSH 凭据）从仓库移除，仅保留本地；脚本和文档中硬编码的 IP / 用户名全部替换为 `<server-ip>` / `<user>` 占位符。
- **.gitignore 补充**：新增 paper/、论文处理临时脚本、ckref.html、start_server.bat 等忽略规则。
- **部署脚本优化**：`server_git_pull_deploy_docker.sh` 无变更时直接退出，不再无意义重启容器；补充 cron 自动部署配置说明。

## [1.3.0] - 2026-05-14

### 新增

- **导航分组**：管理员侧边栏按「数据查看」「填报」「系统」三组渲染，组间带灰色小标题与分隔线，提升功能查找效率。
- **每矿今日填报状态指示器**：历史台账和历史记录页面表格上方显示各矿今日是否已提交数据（绿色圆点 = 已填报，灰色圆点 = 未填报）。
- **系统日志页面**（`/go/logs`）：管理员可在线查看最近 500 行运行日志，方便远程排障。
- **持久化文件日志**：采用 `RotatingFileHandler`（2 MB 滚动、保留 5 份备份），日志持久写入 `data/ymky_system.log`。
- **数据可视化用户可查看历史台账**：「产量数据可视化」角色新增「历史台账」导航入口，以只读模式查看实际产量与能源局产销量数据（不可编辑或删除）。

### 变更

- **台账倒序排列**：历史台账（实际 / 能源局分页）和填报人员历史记录均按提交时间降序排列，最新记录显示在最前面。

### 基础设施

- **数据库双写 + 断线缓冲 + 自动同步**（v1.2.1 后追加）：DB 连接失败时数据暂存本地 Excel，恢复后自动将缺失记录同步回数据库；顶栏显示黄色断线警告。
- **`/health/diag`** 端点：返回 DB 连接状态、各表行数与日期范围、待同步标记。

## [1.2.1] - 2026-05-02

> **版本说明：** **`1.2.0`** 之后的累计修订统一以 **`1.2.1`** 对外发版（不再递增 1.2.2–1.2.4）。

### 修复

- **`GET /export/visual-production.xlsx`**：导出失败时不再 **303** 跳回可视化页（带 `download` 的浏览器常报「下载失败」且无正文）；改为 **`400`** **`text/plain`**，并 **`Content-Disposition`** 建议使用 **`.txt`**，同时 **`flash`** 与 **`logging`** 便于排障。
- 导出页面：用 **`fetch` + Blob** 仅在 **`Content-Type` 为 xlsx** 时触发下载；若为 HTML / 纯文本错误则 **`alert`**，避免把非表格内容存成 **`visual-production.xlsx`** 导致 Excel 报「格式无效」。
- **Kaleido / Chromium（Excel 内嵌图表 PNG）**：
  - **`Dockerfile`**：**`ENV LANG=C.UTF-8 LC_ALL=C.UTF-8`**；补充 **`libgbm1`、`libatk*`、`libdrm2`、`libcups2`、`libxcomposite1`、`libasound2`** 等 headless 常用库，并增加 **`dbus`、`at-spi2-core`、`libgtk-3-0`**；安装 **`fontconfig`、`fonts-noto-cjk`、`fonts-wqy-microhei`、`fonts-wqy-zenhei`**（不要用不存在的 **`fonts-noto-cjk-regular`** 包名；Bookworm 上请用 **`fonts-noto-cjk`**）；**`docker/fontconfig/65-ymky-cjk-sans.conf`** 将 **`sans-serif`** 优先映射到中文字体；**`fc-cache -fv`** 后 **`fc-list | grep`** 校验 WenQuanYi / Noto Sans CJK SC 已出现在 fontconfig 中。
  - **`docker-compose.yml`**：**`ymky`** 服务设置 **`shm_size: "512mb"`**（默认 **64MB** 时内置 Chromium 易崩溃）。
  - **`requirements.txt`**：将 **`kaleido`** 限定为 **`<1.0.0`**。误装 **`kaleido>=1`** 会使用 **choreographer + 系统 Chrome**，与本项目 **`kaleido 0.2.x`**（嵌入式 Chromium）及 Dockerfile 假定不符；日志若出现 **`choreographer.browsers.chromium`** 多属此情况。
  - **Plotly**：**`app/dashboard_data.py`** 为图表指定与系统中文字体一致的 **`font.family`**；饼图 **`textposition="outside"`** 须同时设 **`outsidetextfont` / `insidetextfont`**（仅设 **`textfont`** 时外侧中文仍会回退成方块）；柱状/折线对 **坐标轴刻度与图例** 显式 **`tickfont` / `title_font` / `legend.font`**；字体回退链以 **文泉驿 Micro Hei** 为首。**`app/visual_export.py`**：**`XDG_CACHE_HOME` / `LANG` / `FONTCONFIG_PATH`**，且对 **Kaleido 0.x** 向 **`plotly.io.kaleido.scope.chromium_args`** 追加 **`--single-process`、`--font-render-hinting=none`**（Plotly/Kaleido Wiki 推荐在受限容器内定制 Chromium）。
- 导出报错文案：提示重建镜像、`--force-recreate` 及查 **`docker logs`**。
- **生成报表**：「生成并下载」完成后全局「载入中」不再卡住（附件下载不重载文档时 `pageshow` 不会复位遮罩）；报表表单改用 **`data-no-global-busy`**，仍保留按钮 **`data-loading`** 防重复提交与「处理中…」反馈。

### 运维

- **Dockerfile**：**`apt-get update`** 前将 Debian **bookworm / security** 默认源替换为 **清华大学镜像**（`mirrors.tuna.tsinghua.edu.cn`）；**PyPI** 仍由 **`PIP_INDEX_URL`**（Compose 默认为清华）控制。
- **`scripts/server_git_pull_deploy_docker.sh`**：与 **`docker-compose.yml`**、`Dockerfile` 变更联动时会触发 **`docker compose build`**（见脚本内 **`needs_compose_build`**）。

### 文档

- **`docs/CLOUDFLARE_TUNNEL.md`**：外网导出耗时与 **524/522** 等说明。
- **`docs/DOCKER.md`**：**`docker compose build` 的中间层缓存**——仅 **`Dockerfile` / `requirements.txt` / 更早层变更**会令 **`apt`/`pip`** 重跑；常改 **`app/`** 时一般会复用已有层，不必每次重装系统包与 Python 依赖。

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
