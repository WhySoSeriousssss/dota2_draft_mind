# DOTA 2 Draft Mind 部署指南

本文档适用于 Ubuntu VPS，部署架构如下：

```text
Browser
   |
   | HTTP / HTTPS
   v
Nginx :80 / :443
   |
   | reverse proxy
   v
Uvicorn + FastAPI 127.0.0.1:8000
   |-- /api/*       REST API
   |-- /assets/*    React 静态资源
   `-- /*           React SPA
```

当前规模不需要 Docker。使用 `systemd + Nginx` 的部署链路更短，也更方便排查日志。需要多台服务器、CI/CD 或标准化容器环境时，再增加 Docker。

## 1. 部署要求

- Ubuntu 22.04 或 24.04
- Python 3.10+
- Node.js `^20.19.0` 或 `>=22.12.0`
- Git、Nginx
- 至少开放公网端口 `22`、`80`；启用 HTTPS 后还需要 `443`
- Uvicorn 仅监听 `127.0.0.1:8000`，不要直接暴露到公网

云服务商的安全组和服务器防火墙都需要放行相应端口。

## 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip curl
```

安装系统级 Node.js 后确认版本：

```bash
node --version
npm --version
```

如果 Node.js 版本不满足要求，请从 [Node.js 官方下载页](https://nodejs.org/en/download) 安装当前 LTS 版本。不要使用仅对当前 SSH 用户生效、但 systemd 或部署用户不可见的 Node.js 路径。

## 3. 创建部署用户

```bash
sudo useradd --system --create-home --shell /bin/bash dota2
sudo mkdir -p /opt/dota2_draft_mind
sudo chown dota2:dota2 /opt/dota2_draft_mind
```

后续应用文件归 `dota2` 用户所有，Nginx 和 systemd 配置仍由 `root` 管理。

## 4. 获取代码

```bash
sudo -u dota2 git clone \
  https://github.com/WhySoSeriousssss/dota2_draft_mind.git \
  /opt/dota2_draft_mind

cd /opt/dota2_draft_mind
```

评分数据库 `data/derived/draft_score_v1.sqlite3`、英雄信息和位置配置均已由 Git 管理，正常 clone 后即可使用。

确认关键文件存在：

```bash
test -f data/derived/draft_score_v1.sqlite3
test -f metadata/heroes.json
test -f metadata/hero_positions.json
```

## 5. 安装后端

```bash
sudo -u dota2 python3 -m venv /opt/dota2_draft_mind/.venv
sudo -u dota2 /opt/dota2_draft_mind/.venv/bin/pip install --upgrade pip
sudo -u dota2 /opt/dota2_draft_mind/.venv/bin/pip install -e ".[dev]"
```

运行后端测试：

```bash
sudo -u dota2 /opt/dota2_draft_mind/.venv/bin/pytest -q
```

## 6. 构建前端

```bash
cd /opt/dota2_draft_mind/frontend
sudo -u dota2 npm ci
sudo -u dota2 npm test
sudo -u dota2 npm run build
```

生产构建必须生成以下内容：

```bash
test -f /opt/dota2_draft_mind/frontend/dist/index.html
test -d /opt/dota2_draft_mind/frontend/dist/assets
```

生产环境不运行 Vite dev server。FastAPI 会直接提供 `frontend/dist` 中的构建产物。

## 7. 配置环境变量

创建 `/etc/dota2-draft-mind.env`：

```bash
sudo tee /etc/dota2-draft-mind.env >/dev/null <<'EOF'
DRAFT_DATABASE_PATH=/opt/dota2_draft_mind/data/derived/draft_score_v1.sqlite3
DRAFT_HEROES_PATH=/opt/dota2_draft_mind/metadata/heroes.json
DRAFT_HERO_POSITIONS_PATH=/opt/dota2_draft_mind/metadata/hero_positions.json
DRAFT_FRONTEND_PATH=/opt/dota2_draft_mind/frontend/dist
EOF

sudo chmod 640 /etc/dota2-draft-mind.env
sudo chown root:dota2 /etc/dota2-draft-mind.env
```

## 8. 配置 systemd

创建 `/etc/systemd/system/dota2-draft-mind.service`：

```ini
[Unit]
Description=DOTA 2 Draft Mind
After=network.target

[Service]
Type=simple
User=dota2
Group=dota2
WorkingDirectory=/opt/dota2_draft_mind
EnvironmentFile=/etc/dota2-draft-mind.env
ExecStart=/opt/dota2_draft_mind/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

1 GB 内存的 VPS 建议先使用一个 worker。服务器资源充足并经过压测后，可以改为 `--workers 2`。

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dota2-draft-mind
sudo systemctl status dota2-draft-mind --no-pager
```

在服务器本机验证：

```bash
curl -fsS http://127.0.0.1:8000/api/v1/healthz
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/leaderboard
```

查看实时日志：

```bash
sudo journalctl -u dota2-draft-mind -f
```

## 9. 配置 Nginx

创建 `/etc/nginx/sites-available/dota2-draft-mind`：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name _;

    client_max_body_size 20m;

    location /assets/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 120s;
    }
}
```

这里的代理头配置遵循 [Nginx 官方代理模块说明](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。`client_max_body_size` 为后续 OCR 图片上传预留空间。

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/dota2-draft-mind \
  /etc/nginx/sites-enabled/dota2-draft-mind
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

通过公网 IP 访问：

```text
http://<SERVER_IP>
```

验证反向代理：

```bash
curl -I http://<SERVER_IP>/
curl -fsS http://<SERVER_IP>/api/v1/healthz
```

## 10. 防火墙

如果使用 UFW：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

不要开放端口 `8000`。Nginx 与 Uvicorn 在本机环回地址通信。

## 11. 域名与 HTTPS

先在域名服务商处添加 DNS `A` 记录，将域名指向 VPS 公网 IP。DNS 生效后，把 Nginx 中的：

```nginx
server_name _;
```

改成：

```nginx
server_name example.com www.example.com;
```

然后检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

按照 [Certbot 官方 Nginx 指南](https://certbot.eff.org/instructions?os=ubuntufocal&ws=nginx) 安装并申请证书：

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/local/bin/certbot
sudo certbot --nginx -d example.com -d www.example.com
sudo certbot renew --dry-run
```

申请证书前，域名必须已经解析到当前服务器，并且公网端口 `80` 可以访问。

## 12. 更新部署

代码更新后，在服务器执行：

```bash
cd /opt/dota2_draft_mind

sudo -u dota2 git pull --ff-only

sudo -u dota2 .venv/bin/pip install -e ".[dev]"
sudo -u dota2 .venv/bin/pytest -q

cd frontend
sudo -u dota2 npm ci
sudo -u dota2 npm test
sudo -u dota2 npm run build

sudo systemctl restart dota2-draft-mind
sudo systemctl status dota2-draft-mind --no-pager
curl -fsS http://127.0.0.1:8000/api/v1/healthz
```

只有前端代码发生变化时仍然需要运行 `npm run build`。Vite 开发服务器中的页面不会自动成为生产构建。

## 13. 回滚

先找到需要回滚的提交：

```bash
cd /opt/dota2_draft_mind
sudo -u dota2 git log --oneline -10
sudo -u dota2 git switch --detach <COMMIT_ID>
```

然后重新安装、构建并重启：

```bash
sudo -u dota2 .venv/bin/pip install -e ".[dev]"
cd frontend
sudo -u dota2 npm ci
sudo -u dota2 npm run build
sudo systemctl restart dota2-draft-mind
```

恢复最新主分支：

```bash
cd /opt/dota2_draft_mind
sudo -u dota2 git switch main
sudo -u dota2 git pull --ff-only
```

## 14. 常见问题

### systemd 报 `status=203/EXEC`

这表示 `ExecStart` 指向的程序不存在、没有执行权限，或者路径写错。

```bash
sudo systemctl cat dota2-draft-mind
sudo -u dota2 test -x /opt/dota2_draft_mind/.venv/bin/python
sudo -u dota2 /opt/dota2_draft_mind/.venv/bin/python -m uvicorn --version
namei -l /opt/dota2_draft_mind/.venv/bin/python
```

修改 service 文件后必须执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart dota2-draft-mind
```

### Nginx 返回 `502 Bad Gateway`

```bash
sudo systemctl status dota2-draft-mind --no-pager
sudo journalctl -u dota2-draft-mind -n 100 --no-pager
curl -v http://127.0.0.1:8000/api/v1/healthz
sudo tail -n 100 /var/log/nginx/error.log
```

通常是 Uvicorn 没有启动，或者监听地址、端口与 Nginx 配置不一致。

### 后端提示找不到前端入口或静态资源

```bash
cd /opt/dota2_draft_mind/frontend
sudo -u dota2 npm ci
sudo -u dota2 npm run build
ls -la dist/index.html dist/assets
sudo systemctl restart dota2-draft-mind
```

### 页面更新后仍显示旧版本

```bash
curl -fsS http://127.0.0.1:8000/ | grep '/assets/'
sudo systemctl restart dota2-draft-mind
sudo systemctl reload nginx
```

然后在浏览器执行强制刷新。Vite 资源文件名包含内容哈希，新构建正常时不会长期使用旧资源。

### 服务启动后立即退出

```bash
cd /opt/dota2_draft_mind
sudo -u dota2 .venv/bin/python -m uvicorn \
  backend.app.main:app --host 127.0.0.1 --port 8000
```

前台运行可以直接看到路径、数据库或 Python 依赖错误。

## 15. 发布检查清单

- `git pull --ff-only` 成功
- Python 和 Node.js 版本满足要求
- `pytest -q` 通过
- `npm test` 通过
- `npm run build` 通过
- `frontend/dist/index.html` 和 `frontend/dist/assets` 存在
- `systemctl status dota2-draft-mind` 为 `active (running)`
- `nginx -t` 通过
- `/api/v1/healthz` 返回成功
- 首页、排行榜、设置弹窗和推荐接口可以正常使用
- 启用域名后，HTTPS 证书和自动续期测试正常
