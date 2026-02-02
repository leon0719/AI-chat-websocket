# Django Ninja WebSocket Chatbot API

使用 Django Ninja 的 WebSocket 聊天機器人 API，支援 streaming 文字輸出。

## 技術棧

- **Web 框架**: Django 5.2+, django-ninja 1.4+
- **WebSocket**: channels 4.x, channels-redis 4.x
- **資料庫**: PostgreSQL 16 (psycopg 3.x)
- **快取**: Redis 7
- **AI**: OpenAI API (streaming)
- **認證**: JWT (ninja-jwt)
- **ASGI**: uvicorn + daphne

## 快速開始

### 1. 環境設定

```bash
# 複製本地開發環境變數範例
cp .env.local.example .env.local

# 編輯 .env.local，填入必要的設定
# - OPENAI_API_KEY: OpenAI API 金鑰 (必填)
# - SECRET_KEY 和 JWT_SECRET_KEY 已有預設值，可自行更換
```

**生成金鑰方式：**
```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(50))"

# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. 啟動開發環境

本專案使用 Docker 進行本地開發：

```bash
# 啟動所有服務 (PostgreSQL, Redis, API)
make up

# 等待服務啟動後，執行資料庫遷移
make migrate

# 建立管理員帳號
make createsuperuser

# 查看日誌
make logs

# 停止服務
make down
```

## 環境變數

### 本地開發 (`.env.local`)

```bash
# 使用 Docker 內部網路連線
DATABASE_URL=postgresql://chatbot:chatbot@db:5432/chatbot
REDIS_URL=redis://redis:6379/0
DEBUG=true
```

### 生產環境 (`.env.prod`)

```bash
cp .env.prod.example .env.prod
# 編輯 .env.prod 填入正式環境設定
```

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `SECRET_KEY` | Django secret key | - |
| `DEBUG` | 除錯模式 | `false` |
| `ALLOWED_HOSTS` | 允許的主機（逗號分隔） | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL 連線字串 | - |
| `REDIS_URL` | Redis 連線字串 | - |
| `OPENAI_API_KEY` | OpenAI API 金鑰 | - |
| `JWT_SECRET_KEY` | JWT 簽名金鑰 | - |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 有效期（分鐘） | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 有效期（天） | `7` |
| `CORS_ALLOWED_ORIGINS` | CORS 允許的來源（逗號分隔） | `http://localhost:3000` |

## API 端點

### Health Check `/api/health/`

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health/` | 健康檢查 (檢查 DB 和 Redis 連線) |

### 認證 `/api/auth/`

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/register` | 註冊新使用者 |
| POST | `/logout` | 登出（將 token 加入黑名單） |
| GET | `/me` | 取得當前使用者資訊 |

### Token `/api/token/`

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/pair` | 登入取得 JWT（access + refresh） |
| POST | `/refresh` | 刷新 Access Token |

### 對話 `/api/conversations/`

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/` | 列出所有對話（支援分頁） |
| POST | `/` | 建立新對話 |
| GET | `/{id}` | 取得對話詳情 |
| PATCH | `/{id}` | 更新對話 |
| DELETE | `/{id}` | 刪除對話 |
| GET | `/{id}/messages` | 取得訊息列表（支援分頁） |

### WebSocket

**端點**: `ws://localhost:8000/ws/chat/{conversation_id}/`

WebSocket 使用 **In-Band 認證**，連線後透過訊息發送 token，避免 token 出現在 URL 或日誌中。

#### 認證流程

**1. 連線**（不帶 token）:
```
ws://localhost:8000/ws/chat/{conversation_id}/
```

**2. 發送認證訊息**（30 秒內）:
```json
{"type": "auth", "token": "<jwt_access_token>"}
```

**3. 認證成功回應**:
```json
{"type": "auth.success", "conversation_id": "uuid"}
```

#### 聊天訊息

**發送訊息**:
```json
{"type": "chat.message", "content": "你好"}
```

**接收串流回應**:
```json
{"type": "chat.stream", "content": "你", "done": false}
{"type": "chat.stream", "content": "好", "done": false}
{"type": "chat.stream", "content": "", "done": true, "message_id": "uuid"}
```

#### 心跳機制

伺服器每 30 秒發送 ping，客戶端應回應 pong：
```json
// 伺服器 → 客戶端
{"type": "ping"}

// 客戶端 → 伺服器
{"type": "pong"}
```

#### 錯誤訊息

```json
{"type": "chat.error", "error": "錯誤訊息", "code": "ERROR_CODE"}
```

| 錯誤代碼 | 說明 |
|----------|------|
| `INVALID_JSON` | JSON 格式錯誤 |
| `UNKNOWN_TYPE` | 未知的訊息類型 |
| `AUTH_REQUIRED` | 需要先完成認證 |
| `AUTH_FAILED` | 認證失敗（token 無效或過期） |
| `AUTH_TIMEOUT` | 認證超時（30 秒內未完成認證） |
| `NO_CONVERSATION` | 對話不存在或無權存取 |
| `RATE_LIMIT_EXCEEDED` | 超過速率限制（20 條/60 秒） |
| `ALREADY_PROCESSING` | 正在處理上一條訊息 |
| `EMPTY_CONTENT` | 訊息內容為空 |
| `MESSAGE_TOO_LONG` | 訊息超過長度限制 |
| `AI_TIMEOUT` | AI 回應超時 |
| `AI_ERROR` | AI 服務錯誤 |
| `INTERNAL_ERROR` | 內部錯誤 |

## 安全功能

- **密碼複雜度**：至少 12 字元，須包含大小寫字母、數字、特殊字元
- **登入保護**：5 次失敗後鎖定 15 分鐘（django-axes）
- **Token 黑名單**：登出時 token 加入黑名單，使用 Redis TTL 自動清理
- **WebSocket 安全**：
  - In-Band 認證（token 不在 URL 中）
  - 30 秒認證超時
  - 訊息速率限制（20 條/60 秒）
  - 訊息內容清理（XSS 防護）
  - Origin 驗證（生產環境）
- **生產環境安全設定**：
  - HTTPS 強制重導向
  - HSTS（1 年）
  - Secure Cookie
  - CSP Header

## 常用指令

```bash
make help              # 顯示所有可用指令

# 開發環境 (Docker)
make up                # 啟動開發容器 (日常開發用)
make down              # 停止開發容器
make build             # 僅建構開發映像 (不啟動)
make rebuild           # 重新建構並啟動 (修改 Dockerfile 或 pyproject.toml 後使用)
make logs              # 查看所有日誌
make logs-api          # 查看 API 日誌
make logs-db           # 查看資料庫日誌

# 生產環境 (Docker)
make prod-build        # 建構生產映像
make prod-up           # 啟動生產容器
make prod-down         # 停止生產容器
make prod-logs         # 查看生產日誌

# Django 指令 (在開發容器中執行)
make migrate           # 執行資料庫遷移
make makemigrations    # 建立新遷移檔
make shell             # 開啟 Django shell
make createsuperuser   # 建立管理員帳號

# 程式碼品質
make all               # 執行所有檢查
make format            # 格式化程式碼
make lint              # 執行 ruff 檢查
make type-check        # 執行 mypy 型別檢查
make test              # 執行測試
make unused            # 檢查未使用的函式

# 其他
make install           # 安裝本地依賴 (僅供 IDE)
make clean             # 清理快取檔案
make docker-clean      # 清理開發環境 Docker 資料卷
```

## 專案結構

```
backend/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
│
├── config/                     # Django 設定
│   ├── settings/
│   │   ├── base.py             # 基礎設定
│   │   ├── local.py            # 本地開發設定
│   │   └── prod.py             # 生產環境設定
│   ├── urls.py                 # URL 路由
│   └── asgi.py                 # ASGI 入口
│
├── apps/
│   ├── core/                   # 共用工具
│   │   ├── api.py              # Health Check API
│   │   ├── exceptions.py       # 自訂例外
│   │   ├── log_config.py       # Loguru 設定
│   │   ├── middleware.py       # 中介層
│   │   ├── ratelimit.py        # WebSocket 速率限制
│   │   └── schemas.py          # 共用 Schema
│   │
│   ├── users/                  # 使用者管理
│   │   ├── models.py           # User 模型
│   │   ├── auth.py             # JWT 認證
│   │   ├── services.py         # 業務邏輯
│   │   └── api.py              # 認證 API
│   │
│   └── chat/                   # 聊天功能
│       ├── models.py           # Conversation, Message
│       ├── consumers.py        # WebSocket Consumer
│       ├── middleware.py       # WebSocket 認證中介層
│       ├── config.py           # 設定常數
│       ├── services.py         # 業務邏輯
│       ├── api.py              # REST API
│       └── ai/
│           ├── client.py       # OpenAI 封裝
│           └── tokenizer.py    # Token 計算
│
├── docker/
│   ├── docker-compose.dev.yml  # 開發環境 (含 PostgreSQL, Redis)
│   ├── docker-compose.prod.yml # 生產環境 (僅 API)
│   ├── Dockerfile              # 生產映像
│   └── Dockerfile.dev          # 開發映像
│
├── tests/                      # 測試檔案
│   ├── conftest.py             # Pytest fixtures
│   ├── test_auth.py            # 認證測試
│   ├── test_conversations.py   # 對話測試
│   ├── test_websocket.py       # WebSocket 測試
│   └── test_ratelimit.py       # 速率限制測試
│
├── .dockerignore               # Docker 忽略檔案
├── .env.local.example          # 本地開發環境變數範例
├── .env.prod.example           # 生產環境變數範例
├── CLAUDE.md                   # Claude Code 開發指南
└── README.md                   # 本文件
```

## 測試

```bash
# 執行所有測試 (在 Docker 中)
make test

# 執行特定測試
docker compose -f docker/docker-compose.dev.yml exec api pytest tests/test_auth.py -v

# 執行單一測試
docker compose -f docker/docker-compose.dev.yml exec api pytest tests/test_auth.py::TestAuthEndpoints::test_login_success -v
```

## CI/CD

專案使用 GitHub Actions 自動執行：

1. **Lint & Format** - 使用 ruff 檢查程式碼風格
2. **Type Check** - 使用 mypy 檢查型別
3. **Test** - 執行 pytest 測試
4. **Build** - 建構 Docker 映像

Push 到 `main` 或建立 Pull Request 時會自動觸發。

## API 文件

啟動伺服器後，可在以下位置查看自動產生的 API 文件：

- Swagger UI: http://localhost:8000/api/docs
- OpenAPI JSON: http://localhost:8000/api/openapi.json
