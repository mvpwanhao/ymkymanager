# 更新日志

本文档格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

**约定：** **`VERSION`**（仓库根单文件三段式）为本项目**默认对外版本号的唯一真源**；`/health` 返回的 `version` 取自该文件（前缀 `v`），除非设置了 **`YMKY_APP_VERSION`** 覆盖。**向远端推送前**须在 `CHANGELOG.md` 增补本次条目并与 `VERSION`/`commit` 说明一致。

## [1.1.3] - 2026-04-30

### 新增

- 数据可视化「各矿产量占比」饼图：在图表区左上角以文字展示当前所选时间段内**实际总产量**（吨）。

### 修复

- 饼图总产量说明与扇区外侧标签重叠：缩小饼图 `domain`、加大边距、图例移至右侧留白区；明暗主题切换时仅覆盖 `legend.font.color`，保留 Python 中设置的图例位置。
- 饼图布局：`legend.itemwidth` 设为小于 Plotly 下限（30）会导致 `ValueError`，打开「数据可视化」首页报错 500——已改为合法最小值。
- 深浅色主题下图例默认白底：在 `plotly-theme.js` 中为图例设透明背景并与纸面同色区一致；饼图服务端布局同步 `legend.bgcolor`/边框为透明以便首帧一致。

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
