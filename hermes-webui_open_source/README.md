# Hermes WebUI 🖥️

一个基于 Hermes Agent 的 Web Terminal 管理界面，支持双服务器（杭州/东京）切换、模型选择、CLI 终端（PTY）、用量统计等功能。

## ✨ 核心功能

- **双服务器切换**：杭州（国内直连）+ 东京（SSH Tunnel）
- **模型管理**：全局模型选择、Provider CRUD、模型测试连接
- **CLI 终端**：xterm.js PTY 浏览器终端，支持响应式 resize
- **用量统计**：总 Token 用量、逐模型统计、缓存命中率
- **网关控制**：WebUI/API Server/Feishu/Telegram 等网关状态查询

## 🚀 快速开始

### 前置要求

- Node.js >= 16
- Hermes Agent Dashboard >= 0.15.1（必须开启 `--tui` 参数）
- 支持独立的 Python 3.9+

### 本地部署（推荐）

1. 克隆仓库：
```bash
git clone https://github.com/[YourUsername]/hermes-webui.git
cd hermes-webui
```

2. 部署后端代理（生产环境需要）：

```bash
# 安装依赖
pip3 install python-socketserver ptyprocess

# 启动代理（本地端口 8642）
python3 proxy-server.py
```

3. 配置 Nginx 用于 HTTPS 访问：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    root /path/to/hermes-webui;
    index index.html;

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8642;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### HTTPS 自动证书

使用 Certbot 申请 Let's Encrypt 证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 测试部署

访问 `https://your-domain.com`，初始 token 会从 Dashboard 自动获取。

### 设置 systemd 服务（可选）

创建 `/etc/systemd/system/hermes-webui-proxy.service`：

```ini
[Unit]
Description=Hermes WebUI Proxy (Hangzhou)
After=network.target hermes-dashboard.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/hermes-webui
Environment="HZ_BACKEND=http://127.0.0.1:9119"
Environment="TOKEN=\$(curl -s http://127.0.0.1:9119 | grep -oP '__HERMES_SESSION_TOKEN__=\K[^\"]+')"
ExecStart=/usr/bin/python3 /opt/hermes-webui/proxy-server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable hermes-webui-proxy
sudo systemctl restart hermes-webui-proxy
```

## 🔧 配置说明

### Hangzhou 本地模式（快速）

Hangzhou 使用本地 PTY spawn hermes CLI，速度快无跨域消耗：

1. 安装 Hermes Agent Dashboard（确保 `/hermes/hermes-agent/venv/bin/hermes dashboard --tui` 启用）
2. 配置 Nginx 代理到 `/api/pty` WebSocket
3. WebUI 会自动走 Hangzhou 本地 PTY 端点

### Tokyo 跨区域模式

Tokyo 使用 SSH Tunnel 跨服务器，适合跨境场景：

1. 部署 Tokyo Hermes Dashboard（绑定到 `127.0.0.1:9119`）
2. 建立 SSH tunnel（与 Hangzhou 同根配置）
3. Nginx 配置 `/api/pty-tokyo` 路由到 tunnel 端口
4. WebUI 在 Tokyo 模式下自动切换到 tunnel 后端

## 🌐 双服务器切换

WebUI เหมาะสำหรับ多地域部署，支持：

- **Hangzhou（国内）**：`HZ_BACKEND=http://127.0.0.1:9119`
  - 本地 spawn hermes CLI，秒级响应
  - 适合中国大陆用户

- **Tokyo（海外）**：`TOKYO_BACKEND=http://127.0.0.1:9119`
  - SSH tunnel 跨域转发，稳定可靠
  - 适合东南亚/北美用户

切换方式：
1. 页面右上角下拉菜单
2. 前端自动刷新 token + 数据
3. CLI 终端自动切换后端连接

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 开源自由使用 🚀

## 🙏 致谢

- [Hermes Agent](https://github.com/anomalyco/opencode) - 本项目基于 Hermes Agent 开发
- [xterm.js](https://xtermjs.github.io/xterm.js/) - 前端终端容器
- [ECharts](https://echarts.apache.org/) - 用量统计图表库
