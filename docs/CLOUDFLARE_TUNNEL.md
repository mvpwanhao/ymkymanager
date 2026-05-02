# 使用 Cloudflare Tunnel 暴露本机服务（历史文档）

> **当前推荐：** 本项目生产外网穿透已改用 **SakuraFrp + Docker**，详见 **[`SAKURA_TUNNEL.md`](./SAKURA_TUNNEL.md)**。若宿主机曾启用 **`cloudflared`** systemd，迁移后执行：`sudo systemctl disable --now cloudflared`。
>
> 以下内容保留作 Cloudflare 方案参考。

本应用设计为监听 **本机回环地址**，由 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) 在 Cloudflare 边缘终止 TLS，避免在路由器上做端口映射。

## 1. 本机启动应用

在 `ymky_manager` 目录：

```powershell
cd C:\path\to\ymkycoalmanager-main\ymky_manager
python -m pip install -r requirements.txt
```

配置 `.env`（至少 `YMKY_SECRET_KEY` 与密码相关变量），然后：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

仅绑定 `127.0.0.1`，外网不经由本机防火墙直接访问 8080。

## 2. 安装 cloudflared

从 [Cloudflare 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 下载 Windows 版 `cloudflared`，加入 PATH。

## 3. 登录并创建隧道

按官方向导（需已把域名 DNS 托管到 Cloudflare）：

```powershell
cloudflared tunnel login
cloudflared tunnel create ymky-coal
```

## 4. 配置路由到本机

在配置中将子域名指向本地服务，例如：

```yaml
ingress:
  - hostname: coal.example.com
    service: http://127.0.0.1:8080
  - service: http_status:404
```

（具体以 `cloudflared` 当前版本文档为准。）

## 5. 运行隧道进程

```powershell
cloudflared tunnel run ymky-coal
```

将上述进程与 `uvicorn` 一样，用任务计划程序或 NSSM 在开机时拉起更稳妥。

## 6. 安全提醒

- 使用强 `YMKY_SECRET_KEY` 与角色密码。  
- 通过 HTTPS（Tunnel 已提供）访问；勿将 `uvicorn` 绑定到 `0.0.0.0` 且不经隧道直接暴露。  
- 若已为应用配置自定义域名，可在 `.env` 中设置 `YMKY_TRUSTED_HOSTS`（英文逗号分隔，如 `coal.example.com,127.0.0.1,localhost`），防止异常 `Host` 请求；隧道仅指向本机时也可保持留空。  
- 定期备份 `data/` 下 Excel 或数据库。
