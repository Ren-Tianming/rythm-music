# RyThM Music MVP v0.1

<p align="center">
  <img src="frontend/public/rythm-logo.png" alt="RyThM Music logo" width="180">
</p>

RyThM Music 是面向音乐创作者的三语 Web MVP。本版完成音频分析、Cookie
认证、音乐生成演示、作品发布与历史记录，不包含支付功能。

RyThM Music は音楽クリエイター向けの3言語 Web MVPです。音源解析、
Cookie認証、音楽生成デモ、作品公開、履歴を実装し、決済機能は含みません。

## 已实现 / 実装済み

- 中文、日本語、English 三语响应式赛博朋克界面
- Turnstile 人机验证、邮箱激活、一次性密码恢复、Argon2id 密码
- 可撤销 HttpOnly 不透明 Session、设备 IP 脱敏、安全审计流水
- 24 小时空闲 / 14 天绝对 Session 超时、Session 绑定 CSRF 与 Origin/Referer
- 版本化使用条款/隐私政策与注册同意记录
- 用户数据隔离：分析历史和生成记录只返回当前用户的数据
- BPM、Key、RMS、LUFS、波形、Mel 频谱
- Tonnetz 12 维特征 + ONNX Runtime 曲风分类
- 单并发 FIFO 音源解析队列，避免小型 EC2 被并行分析压垮
- 歌词提取：预留 OpenAI-compatible 音频转写接口
- 无外部 Key 时可运行的本地分析总结和短 WAV 生成 Demo
- 作品发布、公开作品流、Founder RyThM 页面、PDF 报告
- FastAPI、PostgreSQL、Redis、Alembic、React、TypeScript、Vite、Docker Compose

## 目录 / 構成

```text
rythm-music/
├── backend/                 FastAPI、音频分析、ONNX、数据库迁移、测试
│   ├── .venv/              Python 依赖安装位置（setup 后生成）
│   └── models/genre/        genre-model.onnx 与元数据
├── frontend/                React + TypeScript + Vite
├── storage/                 上传与生成音频
├── scripts/                 本地安装与启动脚本
└── docker-compose.yml       PostgreSQL / Redis / API / Web
```

## macOS 本地启动 / macOSローカル起動

把工程放到 Desktop 后：

```bash
cd ~/Desktop/rythm-music
chmod +x scripts/*.sh
./scripts/setup_local.sh
```

`setup_local.sh` 会把所有 Python 依赖安装到 `backend/.venv`，不会污染系统
Python。Node 依赖按前端惯例安装到 `frontend/node_modules`。

数据库使用 PostgreSQL。最简单的本地方式是只启动基础设施：

```bash
docker compose up -d postgres redis
```

终端 1：

```bash
./scripts/start_backend.sh
```

终端 2：

```bash
./scripts/start_frontend.sh
```

打开：

- Web：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

也可以一次启动全部服务：

```bash
cp .env.example .env
docker compose up --build
```

Web 地址为 `http://localhost:8080`。

## ONNX 曲风模型 / ONNXジャンルモデル

仓库已接入现有的 GTZAN Log-Mel CNN 模型：

```text
backend/models/genre/genre-model.onnx
```

模型输入为 `float32 [batch, 1, 64, 130]`。后端会按照训练元数据完成：

- 重采样到 22050 Hz
- 切分 10 个 3 秒片段
- 生成 64 × 130 Log-Mel 特征
- 按训练时的公式归一化到 0–1
- 对十个片段的类别概率取平均

模型与预处理配置位于
`backend/models/genre/genre-model.metadata.json`。模型缺失时返回
`NOT_CONFIGURED`；模型或元数据不兼容时返回 `MODEL_ERROR`。

## 歌词提取 / 歌詞抽出

在 `.env` 设置 OpenAI-compatible transcription endpoint：

```dotenv
AUDIO_LYRICS_API_URL=https://api.openai.com/v1/audio/transcriptions
AUDIO_LYRICS_API_KEY=your-key
AUDIO_LYRICS_MODEL=whisper-1
```

未设置时歌词状态为 `NOT_CONFIGURED`，其余分析功能仍正常工作。

## 安全说明 / セキュリティ

- 浏览器认证仅使用随机不透明的 HttpOnly Session Cookie；数据库只保存使用
  `APP_SECRET` 的 HMAC-SHA-256 摘要，生产 Cookie 使用 `__Host-` 前缀。
- 密码长度为 12–128 字符，使用 Argon2id（19 MiB、t=2、p=1）；旧 bcrypt
  用户成功登录后自动升级。
- 修改类请求要求 Cookie、`X-CSRF-Token` 与当前服务端 Session 内的 CSRF
  摘要三者一致，并验证 `Origin` / `Referer`。
- 新账号必须通过 Turnstile 和一次性邮件链接。链接凭证放在 URL fragment，
  前端会在请求前立即清除。
- 生产环境配置不安全时后端会拒绝启动；必须提供 HTTPS 前端地址、Secure
  Cookie、明确的 CORS/CSRF/Host、Turnstile hostname、TLS SMTP，且拒绝常见
  占位值。
- Nginx 设置 CSP、DENY frame、nosniff、Referrer/Permissions Policy、
  HSTS 与认证限流；生产 Compose 不暴露 PostgreSQL、Redis 和后端端口。
- 未发布的生成音乐只允许所有者读取；公开发布后才允许匿名媒体访问。
- 支付、订单、套餐和 Mock Pay 路由未挂载到本版 API。

## 验证 / 検証

GitHub Actions 的 `.github/workflows/ci.yml` 在 PR、推送到 `main` 或手动触发时，
分别执行 backend / frontend 两个独立 job。使用与 Dockerfile 一致的 Python 3.11
和 Node 22；后端安装 `backend/requirements-dev.txt`（包含运行依赖），前端使用
`npm ci` 严格按现有 lockfile 安装，包括类型检查所需的开发依赖。

GitHub Actions は PR・`main` への push・手動実行で backend / frontend を独立して
検証します。Dockerfile と同じ Python 3.11 / Node 22 を使い、後端は既存の開発用
requirements、前端は lockfile から依存関係をインストールします。

CI 仅使用 `contents: read`，不需要 secrets；测试沿用 SQLite 与测试用配置，
不启动 PostgreSQL / Redis。pip / npm 下载缓存按依赖文件更新，缓存不替代安装。
以下任一检查失败都会使对应 job 失败；`npm audit --omit=dev` 不审计仅开发依赖，
前端 `lint` 当前仅执行 TypeScript 类型检查。Python 的间接依赖尚未完全锁定，
且安全数据库会更新，因此相同代码的审计结果也可能变化。

CI に secrets は不要です。テストは SQLite とテスト用設定を使用し、各チェックの
失敗は job の失敗になります。前端の `lint` は型チェックのみ、npm 監査は本番依存のみ
が対象です。Python の間接依存と脆弱性データベースの更新により結果は変化し得ます。
この最小 CI は本番 PostgreSQL / Redis、ARM64、Docker デプロイの動作検証を含みません。

```bash
backend/.venv/bin/python -m pytest -q
backend/.venv/bin/python -m ruff check backend
backend/.venv/bin/python -m bandit -q -r backend/app
backend/.venv/bin/python -m pip_audit --local
npm --prefix frontend audit --omit=dev
npm --prefix frontend run lint
npm --prefix frontend run build
```

真实模型快速验证：

```bash
AUDIO_GENRE_MODEL_PATH=backend/models/genre/genre-model.onnx \
AUDIO_GENRE_MODEL_METADATA_PATH=backend/models/genre/genre-model.metadata.json \
PYTHONPATH=backend backend/.venv/bin/python -c \
'import numpy as np; from app.services.genre import predict_genre; sr=22050; y=np.zeros(sr*3, dtype=np.float32); print(predict_genre(y, sr))'
```

## Docker 一键启动 / Docker 一括起動

```bash
docker compose up --build -d
docker compose ps
```

- Web：`http://localhost:8080`
- API：`http://localhost:8000`
- 停止：`docker compose down`
- 查看日志：`docker compose logs -f backend frontend`

数据库迁移会在 API 启动前自动执行。数据保存在 Docker volumes 中，
普通的 `docker compose down` 不会删除数据。

EC2 `t4g.small`、共享 PostgreSQL、单一宿主机 Nginx 和
`www.rythmmusic.site` 的完整步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 当前边界 / 現在の制約

- 歌词转写需要外部 API Key；没有 Key 时明确显示未配置。
- 本地音乐生成器仅用于打通流程，不等于 Suno 级生成模型。
- 第一版不包含支付功能。
