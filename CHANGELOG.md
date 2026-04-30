# 更新日志

本文档格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

**约定：** 向 `origin`（或团队约定远端）**推送前**，须在本文件写入与本次提交对应的条目（可新增版本号或并入当日版本下的「新增 / 变更 / 修复」），并与 `git commit` 说明一致；勿空推功能改动。

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
