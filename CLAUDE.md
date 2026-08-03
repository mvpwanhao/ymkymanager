# 识图能力

你的底层模型可能不具备原生识图能力。遇到图片时，不要用 Read 工具，改用 vision.js：

```
node vision.js "<图片路径>" "用中文描述这张图片"
```

网络图片用 `--url`：

```
node vision.js --url "<图片链接>" "用中文描述这张图片"
```

## 触发场景
- 用户分享图片路径（本地或网络 URL）
- 消息中出现 "Saved attachments:" 并列出图片
- 用户要求分析、描述、识别图片内容

## 配置信息（已配置完成）
- API 服务：JOJO Code，Base URL 为 `https://jojocode.com/v1`
- 识图模型：`gpt-5.6-luna`
- API Key 已写入 vision.js（该文件已被 .gitignore 忽略，勿提交）

## 配置好之后
用户直接发图片，自动识图，无需手动打命令。