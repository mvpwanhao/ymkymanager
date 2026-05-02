# Cloudflare Tunnel 暴露外网访问

在 **Ubuntu + Docker Compose**（本仓库 **`docker-compose.yml`**）中与 **`ymky`** 同编排运行 **`cloudflared`**；边缘终止 HTTPS，后端走 **Compose 内网** **`http://ymky:8080`**。

> SakuraFRp 备选见 **[`SAKURA_TUNNEL.md`](./SAKURA_TUNNEL.md)**。**不要**同时为同一域名并行开多套穿透，以免造成混乱。

---

## 1. 前提

- 域名 DNS 已由 **Cloudflare** 托管（或至少子域/route 可走 Tunnel）。
- 服务器上项目在 **`~/ymky_manager`**（或其它目录），已通过 **`docker compose up -d`** 跑 **`ymky-manager`**。
- **`YMKY_TRUSTED_HOSTS`**（若启用）中含公网域名，逗号分隔、无端口。

---

## 2. 在 Cloudflare 创建隧道并拿 Token

1. 登录 [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **创建隧道**。  
2. 选 **Docker** 向导，拷贝 **`cloudflared` 令牌**（长串 `eyJ...`）。  
3. 为该隧道添加 **Public Hostname**（如 **`ymky.haolab.top`**），后端服务：
   ```text
   http://ymky:8080
   ```
   **必须**填 Compose **服务名** **`ymky`**（与 `docker-compose.yml` 中 **`services:`** 下第一层键名一致），**不要**写 **`127.0.0.1`** ——`cloudflared` 与 **`ymky` 是两台容器**，若在 tunnel 内向 `127.0.0.1` 转发，打到的是 **`cloudflared` 容器自己**，不是你的应用。  
   （Zero Trust UI 有时会默认 **`http://127.0.0.1:8080`**——那是在本机直连 `cloudflared`、无 Docker Compose 时才合理；本项目务必改成 **`http://ymky:8080`**。）

---

## 3. 服务器 `.env`（勿提交）

在 **`ymky_manager` 项目根 `.env`** 增加：

```env
CLOUDFLARE_TUNNEL_TOKEN=粘贴ZeroTrust里复制的令牌
```

Docker Compose 会把它注入 **`cloudflared`** 容器的环境变量 **`TUNNEL_TOKEN`**，并运行 **`tunnel run`**（与官方 Docker 向导一致）。

### 隧道 UUID ≠ `CLOUDFLARE_TUNNEL_TOKEN`

控制台隧道详情页上的 **隧道 ID**（形如 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）只是标识符，**不能直接当运行令牌**。`cloudflared` 需要的是向导里那一段很长的 **`eyJ...`** JWT。若你只记住了隧道 UUID，任选下面一种方式补齐令牌。

### 用 API + 隧道 ID 换取令牌（可选）

准备一个 **Cloudflare API Token**，权限包含 **Cloudflare Tunnel Write** 或 **Cloudflare One Connectors / cloudflared Write**（任选其一写法以控制台为准）；并记下 **[账户 Account ID]**（仪表盘 URL 或 **Account Home** → 右侧概要里可见）。

在服务器 shell（勿把 API Token 写入仓库日志）：

```bash
CLOUDFLARE_API_TOKEN='你的_API_Token'
CF_ACCOUNT_ID='你的_Account_UUID'
CF_TUNNEL_ID='你的隧道_UUID'

curl -sS "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/cfd_tunnel/${CF_TUNNEL_ID}/token" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"
```

响应 JSON 的 **`result`** 字段即为 `eyJ...` 整串。把它写成 `.env` 中的 **`CLOUDFLARE_TUNNEL_TOKEN=…`**（一行、无引号）。

可选用 **`COMPOSE_PROFILES=cloudflared`**（或 **`cloudflared,natfrp`** 等多 profile，不推荐同时对外同一域名）。

---

## 4. 启动

```bash
cd ~/ymky_manager
docker compose pull cloudflared
docker compose --profile cloudflared up -d
```

查看：

```bash
docker logs cloudflared-tunnel --tail 50
curl -sS https://你的域名/health   # 以实际域名为准
```

---

## 5. 与「宿主机安装 cloudflared」的区别

本项目 **推荐** Compose 内置 **`cloudflared`**：**升级、令牌、与 `ymky` 拉起顺序** 一起管理。

若你已 **purge 掉 APT 安装的 cloudflared**（卸载 `cloudflared` 包、`systemctl` unit 一并删除），以 **本节 Docker 为准**。

---

## 6. Windows / 单机开发（无 Docker）

本机可先跑 **`uvicorn --host 127.0.0.1`**，再在 Windows 安装官方 **`cloudflared`** 二进制执行 **`tunnel run`**，ingress 仍可写 **`http://127.0.0.1:8080`**（无 Compose 时使用本机环回）。

```powershell
cloudflared tunnel login
cloudflared tunnel create ymky-coal
cloudflared tunnel run ymky-coal
```

（路由配置以 Cloudflare 控制台或 `config.yml` 为准。）

---

## 7. 安全提醒

- 使用强 **`YMKY_SECRET_KEY`** 与后台密码。**`CLOUDFLARE_TUNNEL_TOKEN`** 视为机密，轮换后更新 `.env` 并 **`docker compose up -d --force-recreate cloudflared`**。  
- 定期备份 **`data/`**。

---

## 8. 故障：浏览器 **`Error 1016` Origin DNS error**

访客已到达 Cloudflare 边缘，但边缘**无法把你的公网域名与一条「可用的隧道」对上**，就会报 **`1016`**。常见原因与服务端 Ingress 是否正确（已是 `http://ymky:8080`）**无关**。按优先级自查：

### ① `haolab.top` 的区域与 Tunnel 是否在**同一个 Cloudflare 账户**

[Cloudflare 文档说明](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/dns/)：`.cfargotunnel.com` **只会为与该隧道在同一 CF 账户下托管 DNS 的记录**放行。若 **`haolab.top` DNS 在某个账户 A**，而你是在 **账户 B（或另一家 Zero Trust 组织）里建的隧道**，即使用户面板里域名「看起来都对」，访客也会 **`1016`**。

**自检**：Dashboard 左上角选 **`haolab.top` 所在账户** → 进入 **Zero Trust**，确认左上角仍是**同一 Cloudflare 账户**；Tunnel 须在**该账户对应的 Zero Trust** 里创建。**不对就**：把域名迁到正确账户，或在拥有该域名的账户下**新建隧道**并更新 `.env` 令牌、`Public Hostname` 与 DNS。

### ② DNS：**`ymky` 的子域必须与当前隧道绑定**

在同一账户下：

1. **DNS → Records**：**`ymky`** 建议使用 **CNAME**，目标 **`{隧道 UUID}.cfargotunnel.com`**（形如 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.cfargotunnel.com`，与控制台隧道 ID 一致），**代理状态为橙色已代理（Proxied）**。  
2. **删除**与 **`ymky`** 冲突的冗余记录（重复的 **A/CNAME**，或指向别处的旧 **`cfargotunnel`** 路由）。必要时删掉 **`ymky` 记录**，在 **[Zero Trust → Networks → Tunnels → 你的隧道 → Public hostname]** 里删除并重新添加 **`ymky.haolab.top`**，让用户指引台**自动改写** DNS（若控制台提供该项）。  

文档亦说明：**DNS 与隧道是相对独立的**：若连接器停掉或未与正确隧道关联，仍会 **`1016`**（见上文链接同一页）。

### ③ 连接器是否在该隧道下为 **Healthy**

**Zero Trust → Tunnels → 该隧道**：应看到连接器 **在线**。仅宿主机 **`docker logs` 有 Registered** 但若 UI 断开 / 令牌属于**另一条隧道**，仍会对不上。

确认 **`.env` 里令牌对应的隧道**，与配置了 **`ymky.haolab.top`** 的路由是同一条（隧道 ID / 控制台名称一致）。

### ④ 与本应用相关的补充

若隧道已通但浏览器报 **`400`/`Invalid host header`**：检查 **`YMKY_TRUSTED_HOSTS`** 是否包含 **`ymky.haolab.top`**（无端口）。

---

## 9. 换新隧道（旧隧道排查成本高时）

**可以**。同一域名换一条隧道往往能避开历史 DNS / 控制台状态不一致。**同一公网主机名同一时间只能挂在一个隧道上**，建议按顺序做：

1. **Zero Trust** → **Networks** → **Tunnels** → **创建隧道**，命名自定（例如 `ymky_manager_v2`）。  
2. 在 **旧隧道**里 **删除** **`ymky.haolab.top`** 的 **Public hostname**（或整条不再用的路由），避免与新区冲突。  
3. 在 **新隧道**里添加 **Public hostname**：**`ymky.haolab.top`** → **`http://ymky:8080`**，保存。  
4. 复制新隧道的 **「在 Docker 中运行」** 令牌（`eyJ...`），写入服务器 **`~/ymky_manager/.env`** 的 **`CLOUDFLARE_TUNNEL_TOKEN=`**（覆盖旧值，勿提交仓库）。  
5. **DNS**（`haolab.top`）里 **`ymky`** 的 **CNAME** 目标改为 **新隧道的** **`{新隧道 UUID}.cfargotunnel.com`**，保持 **已代理（橙色云）**；删掉同名的重复 **A/CNAME**。若控制台提供「通过隧道自动配置 DNS」，可优先用向导覆盖。  
6. 服务器执行：  
   `cd ~/ymky_manager && docker compose --profile cloudflared up -d --force-recreate cloudflared`  
7. 确认 **`docker logs cloudflared-tunnel`** 里 **`tunnelID=`** 与 **新隧道 UUID** 一致，且 **`Registered tunnel connection`** 正常后，再测 **`https://ymky.haolab.top/health`**。  
8. 旧隧道在控制台 **停用或删除**；旧令牌视为已泄露的应 **在隧道侧轮换**（即使不再使用也建议清理）。

应用与 **`docker-compose.yml`** 无需改结构，只换 **令牌 + DNS CNAME + 控制台路由** 即可。
