# AI Chat WebSocket

基於 WebSocket 的即時 AI 聊天應用，支援串流式回應與多種 GPT 模型選擇。

## 功能特色

- **即時串流回應** - 透過 WebSocket 實現 AI 回應的逐字串流顯示
- **多模型支援** - 支援 GPT-4o、GPT-4o-mini、GPT-4-turbo、GPT-3.5-turbo
- **安全認證** - JWT Token 認證，支援自動刷新與黑名單機制
- **對話管理** - 建立、編輯、刪除對話，支援自訂系統提示詞
- **Markdown 渲染** - 支援 GitHub 風格 Markdown 與程式碼語法高亮
- **響應式設計** - 現代化 UI，支援深色模式

## 技術棧

### 後端

| 類別 | 技術 |
|------|------|
| 框架 | Django 5.2、Django Ninja、Channels |
| 資料庫 | PostgreSQL 16 |
| 快取 | Redis 7 |
| AI | OpenAI API、Tiktoken |
| 認證 | JWT (Django Ninja JWT) |
| 安全 | Django-Axes、nh3 |

### 前端

| 類別 | 技術 |
|------|------|
| 框架 | React 19、TypeScript、Vite |
| 狀態管理 | Zustand、TanStack React Query |
| UI | Tailwind CSS、Radix UI |
| 表單 | React Hook Form、Zod |
| Markdown | react-markdown、react-syntax-highlighter |

## 專案結構

```
AI-chat-websocket/
├── backend/                     # Django 後端
│   ├── apps/
│   │   ├── core/               # 健康檢查、日誌
│   │   ├── users/              # 使用者認證
│   │   └── chat/               # 聊天功能、WebSocket
│   ├── config/                 # Django 設定
│   ├── docker/                 # Docker 配置
│   └── tests/                  # 測試
├── frontend/                    # React 前端
│   └── src/
│       ├── api/                # API 客戶端
│       ├── components/         # UI 元件
│       ├── hooks/              # 自訂 Hooks
│       ├── stores/             # Zustand 狀態
│       ├── pages/              # 頁面
│       └── types/              # TypeScript 型別
└── README.md
```

## 快速開始

### 環境需求

- Python 3.12+
- Node.js 20+ 或 Bun
- Docker & Docker Compose
- PostgreSQL 16
- Redis 7

### 後端設定

```bash
cd backend

# 複製環境變數範本
cp .env.example .env.local

# 啟動開發環境 (PostgreSQL + Redis + API)
make up

# 執行資料庫遷移
make migrate
```

### 前端設定

```bash
cd frontend

# 安裝依賴
bun install  # 或 npm install

# 複製環境變數範本
cp .env.example .env

# 啟動開發伺服器
bun dev  # 或 npm run dev
```

應用程式將在以下位置運行：
- 前端：http://localhost:5173
- 後端 API：http://localhost:8000/api
- WebSocket：ws://localhost:8000/ws

## 環境變數

### 後端 `.env.local`

```bash
# 必填
SECRET_KEY=your-django-secret-key
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-openai-api-key
JWT_SECRET_KEY=your-jwt-secret-key

# 選填
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

### 前端 `.env`

```bash
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000
```

## API 文檔

### 認證端點

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/auth/register` | 使用者註冊 |
| POST | `/api/auth/token/pair` | 登入取得 Token |
| POST | `/api/auth/token/refresh` | 刷新 Access Token |
| GET | `/api/auth/me` | 取得使用者資訊 |
| POST | `/api/auth/logout` | 登出 |

### 對話端點

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/conversations/` | 列出對話 |
| POST | `/api/conversations/` | 建立對話 |
| GET | `/api/conversations/{id}` | 取得對話詳情 |
| PATCH | `/api/conversations/{id}` | 更新對話 |
| DELETE | `/api/conversations/{id}` | 刪除對話 |
| GET | `/api/conversations/{id}/messages` | 取得訊息列表 |

### 健康檢查

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/health/` | 檢查服務狀態 |

## WebSocket 協議

### 連線與認證

```javascript
// 1. 建立連線
const ws = new WebSocket('ws://localhost:8000/ws/chat/{conversation_id}/');

// 2. 發送認證訊息 (30 秒內)
ws.send(JSON.stringify({
  type: 'auth',
  token: 'your-jwt-access-token'
}));

// 3. 認證成功回應
// { "type": "auth.success", "conversation_id": "uuid" }
```

### 傳送訊息

```javascript
// 發送聊天訊息
ws.send(JSON.stringify({
  type: 'chat.message',
  content: '你好，請介紹一下自己'
}));

// 接收串流回應
// { "type": "chat.stream", "content": "你", "done": false }
// { "type": "chat.stream", "content": "好", "done": false }
// { "type": "chat.stream", "content": "", "done": true, "message_id": "uuid" }
```

### 錯誤代碼

| 代碼 | 說明 |
|------|------|
| `AUTH_REQUIRED` | 需要先完成認證 |
| `AUTH_FAILED` | Token 無效或過期 |
| `AUTH_TIMEOUT` | 認證超時 (30 秒) |
| `RATE_LIMIT_EXCEEDED` | 超過速率限制 (20 條/60 秒) |
| `MESSAGE_TOO_LONG` | 訊息超過長度限制 |
| `AI_ERROR` | AI 服務錯誤 |

## 開發指令

### 後端

```bash
make up                 # 啟動開發環境
make down               # 停止容器
make logs               # 查看日誌
make migrate            # 執行遷移
make makemigrations     # 建立遷移
make shell              # Django Shell
make test               # 執行測試
make lint               # 程式碼檢查
make format             # 程式碼格式化
make type-check         # 型別檢查
```

### 前端

```bash
bun dev                 # 開發伺服器
bun build               # 生產建置
bun preview             # 預覽建置
bun lint                # 程式碼檢查
bun format              # 程式碼格式化
bun type-check          # 型別檢查
```

## 安全特性

- **JWT 認證** - Access Token (15 分鐘) + Refresh Token (7 天)
- **Token 黑名單** - 登出時將 Token 加入黑名單
- **蹲力保護** - 5 次登入失敗後鎖定 15 分鐘
- **XSS 防護** - 使用 nh3 清理 HTML 內容
- **速率限制** - WebSocket 訊息限制 20 條/60 秒
- **CORS** - 限制允許的來源

## Docker 部署

### 開發環境

```bash
docker compose -f docker/docker-compose.dev.yml up
```

### 生產環境

```bash
docker compose -f docker/docker-compose.prod.yml up
```

## 授權條款

MIT License
