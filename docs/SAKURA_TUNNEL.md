# SakuraFrp 外网访问（Docker）

使用官方镜像 **`natfrp.com/launcher`**，与 **`docker-compose.yml`** 中的应用服务 **`ymky`**（宿主机 **`127.0.0.1:8080`**）配合，替代 Cloudflare Tunnel。

> **迁移自 Cloudflare：**停用宿主机上的 `cloudflared` systemd 单元（若有）：`sudo systemctl disable --now cloudflared`。

## 前置条件

- **Linux + Docker Compose**：启动器镜像需 **`network_mode: host`**，才能把你配置的隧道转发目标写成 **`127.0.0.1:8080`**（与 Docker 映射到宿主机的业务端口一致）。参见 [官方 Docker 说明](https://doc.natfrp.com/launcher/usage.html)。
- `.env` 在项目根目录，且 **勿提交 Git**。

## 1. `.env` 必填

在 `.env` 末尾增加 Sakura「用户信息」页的 **访问密钥**：

```env
NATFRP_TOKEN=你的访问密钥
```

启用 **`--profile natfrp`** 或 **`COMPOSE_PROFILES=natfrp`** 时 **必须**有有效 `NATFRP_TOKEN`；若留空就拉起 `sakurafrp`，容器会失败，请查看 **`docker logs sakurafrp`**。

若在面板使用 **HTTPS / 自定义域名**，还需让应用放行 Host（见下文 **§4**）。

可选：启用启动器文档中的 **远程管理**，可在单机 `docker run` 命令里增加 `-e NATFRP_REMOTE=<≥8字符密码>`；若使用 Compose，可复制 **`sakurafrp`** 服务段到本机 **`docker-compose.override.yml`** 并追加 **`environment`** 中的 **`NATFRP_REMOTE`**（勿把密码提交仓库）。

## 2. 启动命名容器 `sakurafrp`

在项目根：

```bash
mkdir -p natfrp
docker compose pull
docker compose --profile natfrp up -d
```

若希望 **`docker compose up -d`**（例如 cron 部署脚本）**顺带拉起穿透**，可在 `.env` 增加：

```env
COMPOSE_PROFILES=natfrp
```

不写该项时：仅 **`docker compose up -d`** 默认**不会**启动 **`sakurafrp`**，需按需加上 **`--profile natfrp`**。

查看启动器日志（首次会出现 **WebUI 端口与密码**，仅一次）：

```bash
docker logs sakurafrp
```

浏览器打开 **`https://127.0.0.1:<WebUI端口>`**（新版本默认端口通常为 **7102**，以日志为准）。

## 3. 面板里隧道指向本机

### 必须用 **HTTP(S) 隧道**，不能用纯 **TCP** 当你的网站域名

要使 **`http(s)://ymky.haolab.top`**（**不带端口**）能访问本机 **`8080`** 上的 Web 应用， Sakura **隧道类型必须是「HTTP 隧道」或「HTTPS 隧道」**，并在隧道上 **绑定域名** **`ymky.haolab.top`**。

若创建的是 **`TCP 隧道`**，日志里会出现类似 **`隧道启动中: [xxx, tcp]`**、**`TCP 隧道启动成功`**，外网只能靠 **`域名:远端端口`** 或 **`节点:端口`**（如 **`frp-gap.com:10539`**）访问，**不会做按域名的 HTTP 路由**。此时你把 DNS **`CNAME` 到 `frp-gap.com`** 后浏览器访问 **`http://ymky.haolab.top`** 仍会命中樱花 **HTTP 入口**，但因没有对应 HTTP 映射而返回 **`503`** ——这与 Docker 无关。

**自检：**

```bash
docker logs sakurafrp 2>&1 | grep -E '隧道启动中|TCP 隧道|HTTP'
```

若看到 **`tcp`** 而期望用裸域名建站，请到 **[樱花管理面板隧道列表](https://www.natfrp.com/tunnel/)** **新建 HTTP/HTTPS 隧道**（本地 **`127.0.0.1:8080`**，绑定 **`ymky.haolab.top`**），再在启动器 WebUI **启用该隧道**，并视情况停用旧 **TCP** 隧道。

### 绑定与 DNS

创建或编辑 **HTTP(S)** 隧道时：

- **本地 IP**：`127.0.0.1`
- **本地端口**：`8080`

自定义域名：在 Sakura **隧道绑定 `ymky.haolab.top`**，再在阿里云等处 **`CNAME` → 面板给定目标**（常见为节点相关主机名例如 **`frp-gap.com`**，**不要带 `:端口`**）。

**关键（否则公网常为 `503` + `Server: SakuraFrp`）：**

1. **类型为 HTTP/HTTPS**，且绑定域名与访问域名 **完全一致**；纯 TCP 不适用「仅用 CNAME + 浏览器默认端口」建站。  
2. **务必打开隧道卡片右上角「启用」开关**——未启用时宿主上 **`docker exec sakurafrp ps`** 看不到 **`frpc`** 进程。  
3. 启用后：**`DNS 生效且节点一致`**（参见 [樱花：无法访问](https://doc.natfrp.com/faq/site-inaccessible.html)）；本机 **`curl http://127.0.0.1:8080/health`** 应 **`ok`**。

若在 WebUI 已登录 Sakura，建议将访问密钥写入 **`.env` 的 `NATFRP_TOKEN`**（勿向他人泄露），可选用仓库脚本 **`scripts/sync_natfrp_token_to_env.sh`**——在跑着 **`sakurafrp`** 时执行，从容器 **`/run/config.json`** 同步一行到 **`.env`**。

## 4. `YMKY_TRUSTED_HOSTS`

若在 `.env` 中配置了 **Host 白名单**，必须把浏览器访问域名写入（英文逗号分隔，**不含端口**），例如：

```env
YMKY_TRUSTED_HOSTS=ymky.haolab.top,127.0.0.1,localhost
```

修改后重启应用容器：

```bash
docker compose up -d --force-recreate ymky
```

## 5. 配置持久化

Compose 已将宿主 **`./natfrp`** 挂载到容器内 **`/run`**，用于保存启动器生成的配置；目录已列入 **`.gitignore`**。

## 6. 镜像拉取失败时可替换的标签

官方文档建议在拉取 **`natfrp.com/launcher`** 失败时可改用：`natfrp/launcher`、`ghcr.io/natfrp/launcher` 等——修改 **`docker-compose.yml`** 中 `image:` 行即可。

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| **公网 `503`、`Server: SakuraFrp`，本机 `127.0.0.1:8080` 正常** | 常见原因：**建了 TCP 隧道却用域名当网站** ——改用 **HTTP/HTTPS** 隧道并绑定域名；或 **DNS 指向节点与隧道节点不一致**（见上文 **§3**）；或隧道未启用。 |
| **`Bind … 7102`** | 宿主已有程序占用 WebUI 端口；关闭冲突进程或按官方手册改监听端口。 |
| **穿透连上但页面 400 / Invalid host** | 核对 **§4** `YMKY_TRUSTED_HOSTS`。 |
| **仅 Linux** | macOS / Windows Docker 不推荐 `network_mode: host`，请改用官方桌面启动器或非 Docker `frpc`。 |
