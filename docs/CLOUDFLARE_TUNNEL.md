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
   **必须**填 Compose **服务名** **`ymky`**（与 `docker-compose.yml` 中 **`services:`** 下第一层键名一致），**不要**写 **`127.0.0.1`** ——tunnel 容器与 API 容器在同一 bridge 网络上，用服务名 DNS 互通。

---

## 3. 服务器 `.env`（勿提交）

在 **`ymky_manager` 项目根 `.env`** 增加：

```env
CLOUDFLARE_TUNNEL_TOKEN=粘贴ZeroTrust里复制的令牌
```

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
