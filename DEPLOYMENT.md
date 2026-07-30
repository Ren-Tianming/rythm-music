# RyThM Music 单机部署

目标环境是单台 AWS EC2 `t4g.small`（ARM64），同时运行 RyThM Music 与
RyThM Chatbot。Music 使用 `https://www.rythmmusic.site`。只有宿主机
Nginx 监听公网 `80/443`，两个 Web 容器只绑定回环地址。

AWS 当前规格中 `t4g.small` 为 2 vCPU、2 GiB 内存。项目固定的
`onnxruntime 1.22.1`、`numba 0.61.2`、`llvmlite 0.44.0` 均提供
CPython 3.11 Linux ARM64 wheel：
[AWS](https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html) ·
[ONNX Runtime](https://pypi.org/project/onnxruntime/1.22.1/) ·
[Numba](https://pypi.org/project/numba/0.61.2/) ·
[llvmlite](https://pypi.org/project/llvmlite/0.44.0/)。

## 1. 最终拓扑

```text
Internet
   |
Host Nginx :80/:443
   |-- www.rythmmusic.site  -> 127.0.0.1:8080 -> Music frontend -> Music backend
   `-- chat.rhythmusic.site -> 127.0.0.1:8081 -> Chatbot web    -> Chatbot backend

Docker internal networks
   |-- Music Redis（不发布端口）
   `-- shared PostgreSQL（不发布端口）
         |-- rythm_music database / rythm_music role
         `-- rythm_chatbot database / rythm_chatbot role
```

一个 PostgreSQL 容器可以供两个服务使用，但必须保留两个数据库和两个登录
角色。这样可以降低 `t4g.small` 的常驻内存；代价是数据库重启、故障和备份窗口
会同时影响两个服务。流量增长后应优先迁移到 RDS。

资源上限已经写入 Compose：共享 PostgreSQL 320 MiB、Music Redis 64 MiB、
Music API 768 MiB、Music Web 64 MiB；Chatbot 覆盖配置把 API/Web 限制为
384/64 MiB。Music API 只运行一个 Uvicorn worker，音源解析并发固定为 1，
其余解析请求进入长度为 8 的 FIFO 等待队列。普通页面和账户请求仍可继续处理。

## 2. 主机准备

建议使用 Ubuntu 24.04 ARM64，挂载持久 EBS，并配置 Elastic IP。安全组只开放：

- `80/tcp`、`443/tcp`：公网；
- `22/tcp`：仅管理 IP；
- 不开放 `5432`、`6379`、`8000`、`8080`、`8081`。

2 GiB 内存构建科学计算和 ONNX 镜像比较紧张，先添加 2 GiB swap：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

安装 Docker Engine、Docker Compose plugin、Nginx 和 Certbot。部署用户需可运行
Docker，但不要加入不受信任的系统用户。

建议目录：

```text
/opt/rythm-music
/opt/rythm-chatbot
```

ONNX 文件
`backend/models/genre/genre-model.onnx` 已纳入仓库和 Backend 镜像，不需要在
EC2 上另行挂载，也不能从部署包忽略。

## 3. DNS 与唯一公共 Nginx

将以下 DNS A/AAAA 记录指向同一个 EC2 Elastic IP：

- `www.rythmmusic.site`
- `chat.rhythmusic.site`（当前 Chatbot 使用的域名）

首次签发证书时，可以暂时停止 Nginx 后使用 Certbot standalone：

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone -d www.rythmmusic.site
sudo certbot certonly --standalone -d chat.rhythmusic.site
```

复制两个虚拟主机。Music 配置在本仓库；Chatbot 配置继续使用 Chatbot 仓库中的
文件。

```bash
sudo cp /opt/rythm-music/deploy/nginx/www.rythmmusic.site.conf \
  /etc/nginx/sites-available/www.rythmmusic.site.conf
sudo cp /opt/rythm-chatbot/deploy/nginx/chat.rhythmusic.site.conf \
  /etc/nginx/sites-available/chat.rhythmusic.site.conf
sudo ln -s /etc/nginx/sites-available/www.rythmmusic.site.conf \
  /etc/nginx/sites-enabled/www.rythmmusic.site.conf
sudo ln -s /etc/nginx/sites-available/chat.rhythmusic.site.conf \
  /etc/nginx/sites-enabled/chat.rhythmusic.site.conf
sudo nginx -t
sudo systemctl enable --now nginx
```

删除或禁用 Nginx 的默认站点。不要在任何 Compose 文件中发布宿主机
`80:80` 或 `443:443`；当前 Music 为 `127.0.0.1:8080:80`，Chatbot 为
`127.0.0.1:8081:80`。

## 4. 生产密钥

Music 创建两个仅本机可读的环境文件：

```bash
cd /opt/rythm-music
cp .env.production.example .env.production
cp deploy/shared-postgres.env.example deploy/shared-postgres.env
chmod 600 .env.production deploy/shared-postgres.env
```

使用不同的随机值替换全部 `replace-with-*`。数据库密码建议使用 URL 安全的
十六进制，避免连接 URL 转义问题：

```bash
openssl rand -hex 32
```

`APP_SECRET`、PostgreSQL 管理密码、Music 数据库密码、Chatbot 数据库
密码必须各不相同。Turnstile 允许的 hostname 必须包含
`www.rythmmusic.site`，SMTP 必须使用真实 TLS 服务和已验证的发件地址。

生产启动校验会拒绝空值、`replace-with-*`、`change-me`、`example.com`、
非 HTTPS 来源、非 `__Host-` Cookie 名称和解析并发大于 1 的配置。

Chatbot 的 `/opt/rythm-chatbot/.env` 仍保存 Chatbot 自身的生产配置；共享数据库
连接由覆盖文件注入，不需要把 Music 的应用密钥复制给 Chatbot。

## 5. 首次启动 Music 和共享数据库

先验证解析后的配置：

```bash
cd /opt/rythm-music
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml config --quiet
```

为减少小实例构建峰值，顺序构建，再启动：

```bash
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml build backend
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml build frontend
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml up -d
```

PostgreSQL 第一次初始化时会创建两个数据库/角色。Alembic 成功后 Backend 才会
启动。

```bash
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml ps
curl --fail http://127.0.0.1:8080/health
curl --fail https://www.rythmmusic.site/ready
```

不要使用 `docker compose down -v`，它会删除共享数据库和生成音频卷。

## 6. 让 Chatbot 使用共享 PostgreSQL

覆盖文件需要 Compose 2.24 或更新版本（使用 `!reset` / `!override`）。先检查：

```bash
docker compose version
```

全新 Chatbot 可直接启动：

```bash
cd /opt/rythm-chatbot
docker compose \
  --env-file /opt/rythm-music/deploy/shared-postgres.env \
  --env-file .env \
  -f docker-compose.yml \
  -f /opt/rythm-music/deploy/chatbot-shared-db.override.yml \
  config --quiet
docker compose \
  --env-file /opt/rythm-music/deploy/shared-postgres.env \
  --env-file .env \
  -f docker-compose.yml \
  -f /opt/rythm-music/deploy/chatbot-shared-db.override.yml \
  up -d --build backend web
```

覆盖后 `db` 服务不会启动，Backend 连接共享网络中的 `rythm-postgres`。Chatbot
自己的内部网络仍保留，用于 Web 到 Backend。

### 已有 Chatbot 数据的迁移

迁移前先使用 Chatbot 原有 `deploy/backup.sh` 生成并验证 gzip 备份，然后停止
旧栈；普通 `down` 不会删除旧 volume。

```bash
cd /opt/rythm-chatbot
RYTHM_PROJECT_DIR=/opt/rythm-chatbot ./deploy/backup.sh
docker compose down
```

在 Chatbot 尚未连接新库之前，将备份导入第一次初始化后仍为空的
`rythm_chatbot`：

```bash
gzip -dc /path/to/rythm-backup.sql.gz | docker compose \
  --env-file /opt/rythm-music/deploy/shared-postgres.env \
  --env-file /opt/rythm-music/.env.production \
  -f /opt/rythm-music/docker-compose.prod.yml \
  exec -T postgres sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$CHATBOT_POSTGRES_DB"'
```

导入完成后再使用覆盖配置启动 Chatbot。其 entrypoint 会执行 Chatbot 自己的
Alembic migration。旧 Chatbot volume 保留到新库、登录和数据抽查全部确认后再
决定是否删除。

## 7. 备份

共享数据库备份脚本会分别生成 Music、Chatbot 的 custom-format dump，以及
不含角色密码的 globals 文件：

```bash
sudo install -d -m 700 -o rythm -g rythm /var/backups/rythm-postgres
sudo cp deploy/rythm-postgres-backup.service /etc/systemd/system/
sudo cp deploy/rythm-postgres-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rythm-postgres-backup.timer
```

至少执行一次手工备份并把副本同步到另一故障域：

```bash
./deploy/backup-shared-postgres.sh
sudo systemctl list-timers rythm-postgres-backup.timer
```

恢复会覆盖数据，必须先停止两个 Backend，并在副本环境演练
`pg_restore --clean --if-exists`。不要把“存在备份文件”等同于“能够恢复”。

## 8. 更新、监控与回滚

更新前依次执行：

1. 运行共享数据库备份；
2. `docker compose ... config --quiet`；
3. 顺序构建镜像；
4. `docker compose ... up -d`；
5. 检查 `/ready`、登录、密码重置、一次音源解析和公开作品播放。

常用检查：

```bash
docker stats --no-stream
docker compose \
  --env-file deploy/shared-postgres.env \
  --env-file .env.production \
  -f docker-compose.prod.yml logs --tail=200 backend postgres redis
sudo journalctl -u nginx --since "30 minutes ago"
```

告警至少覆盖磁盘、内存、swap、容器重启、`/ready`、5xx、解析队列满和备份失败。
若频繁使用 swap、出现 OOM、队列经常满或两个服务同时有真实流量，应升级到
`t4g.medium`，随后优先把 PostgreSQL 迁移到 RDS、生成音频迁移到 S3。

## 9. 公开上线前人工确认

- Turnstile、SMTP、DNS、证书续期和备份恢复已真实验证；
- `terms.html` / `privacy.html` 的版本与 `AUDIO_TERMS_VERSION` 一致；
- 根据实际运营主体补充运营者信息、联系窗口、外部处理商和数据保存期限，并由
  适用法域的专业人员复核；
- 旧 Session/验证链接会因新的 `APP_SECRET` HMAC 基线失效，提前安排一次
  全员重新登录；
- 确认 Music 显示名始终为 `RyThM Music`，Docker 项目标识为
  `rythm-music`，两者用途不同。
