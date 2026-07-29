# RyThM Music deployment

## 中文

### 本地验收

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8080/health
curl http://localhost:8000/ready
```

所有长期数据位于 `postgres_data`、`redis_data`、`uploads` 和
`generated` volumes。停止服务不会删除数据：

```bash
docker compose down
```

只有明确需要清空全部本地数据时才使用 `docker compose down -v`。

### AWS EC2 单机部署

推荐最初使用一台安装 Docker Engine 与 Compose 的 EC2，前面放置
Application Load Balancer，并由 ACM 提供 HTTPS 证书。

1. 将域名指向 ALB。
2. ALB 的 443 listener 转发到 EC2 的 TCP 80。
3. EC2 安全组只允许 ALB 访问 80，SSH 只允许管理 IP。
4. 不要向公网开放 PostgreSQL 5432、Redis 6379 或后端 8000。
5. 保持 ALB 的 `X-Forwarded-For` append 模式；Nginx 只信任私网代理并取
   ALB 最后追加的客户端地址。
6. 复制生产环境模板并填写随机密码和真实域名：

```bash
cp .env.production.example .env.production
```

至少必须修改：

- `POSTGRES_PASSWORD`
- `AUDIO_FRONTEND_URL`、`AUDIO_CORS_ORIGINS`、`AUDIO_ALLOWED_HOSTS`
- `VITE_TURNSTILE_SITE_KEY`、`AUDIO_TURNSTILE_SECRET_KEY`
- `AUDIO_TURNSTILE_EXPECTED_HOSTNAMES`
- `AUDIO_SMTP_HOST`、`AUDIO_SMTP_USERNAME`、`AUDIO_SMTP_PASSWORD`
- `AUDIO_SMTP_FROM_EMAIL`

启动：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

生产配置启用了 Secure Cookie，因此必须通过 HTTPS 访问。ALB 可在 HTTPS
入口终止 TLS，再通过私有网络转发到前端容器。生产 Compose 只发布前端 80；
PostgreSQL、Redis 与后端 API 只存在于 Docker 内部网络。

### 更新与回滚

部署更新前先备份数据库。更新代码后：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

迁移容器会先执行 Alembic，成功后 API 才启动。

本次认证迁移会让所有旧 JWT/Refresh Cookie 立即失效。为避免锁死已有用户，
迁移前已处于 `ACTIVE` 的账号会保留访问权限并标记为已验证；迁移后新注册账号
必须完成邮件激活。

建议在正式环境进一步使用：

- ECR 保存带版本号的镜像；
- RDS PostgreSQL 替代容器数据库；
- ElastiCache Redis 替代容器 Redis；
- S3 保存生成音频；
- CloudWatch 收集日志和告警；
- AWS Secrets Manager 或 SSM Parameter Store 保存密钥。

当前生产 Compose 适合初期单机部署。扩展到多台 API 服务器前，应先把生成音频
迁移到 S3，并把异步音乐生成任务交给独立 worker/队列。

## 日本語

### ローカル確認

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8080/health
curl http://localhost:8000/ready
```

永続データは `postgres_data`、`redis_data`、`uploads`、`generated`
volumeに保存されます。通常の `docker compose down` では削除されません。

### AWS EC2への初期デプロイ

最初はDocker EngineとComposeを導入したEC2を1台使用し、前段に
Application Load BalancerとACMのHTTPS証明書を配置する構成を推奨します。

1. ドメインをALBへ向けます。
2. ALBの443 listenerからEC2の80番へ転送します。
3. EC2の80番はALBからのみ、SSHは管理用IPからのみ許可します。
4. PostgreSQL 5432、Redis 6379、API 8000を公開しないでください。
5. ALBの `X-Forwarded-For` はappendモードを維持してください。Nginxは
   private networkのproxyだけを信頼し、ALBが最後に追加したclient IPを使います。
6. 本番環境ファイルを作成します。

```bash
cp .env.production.example .env.production
```

`POSTGRES_PASSWORD`、実ドメインの `AUDIO_FRONTEND_URL` /
`AUDIO_CORS_ORIGINS` / `AUDIO_ALLOWED_HOSTS`、Turnstile の Site/Secret Key
と hostname、TLS 対応 SMTP の接続情報と送信元アドレスは必ず設定してください。

起動：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

本番設定ではSecure Cookieが有効なため、HTTPS経由で利用してください。
本番Composeが公開するのはフロントエンドの80番だけで、PostgreSQL、Redis、
バックエンドAPIはDocker内部ネットワークからのみ到達できます。

本格的な拡張時には、PostgreSQLをRDS、RedisをElastiCache、生成音声をS3、
秘密情報をSecrets ManagerまたはSSMへ移行することを推奨します。

今回の認証migrationでは旧JWT/Refresh Cookieがすべて即時失効します。既存
ユーザーのlockoutを避けるため、migration前に `ACTIVE` だったアカウントは
確認済みとして維持され、migration後の新規登録だけがメール確認必須になります。
