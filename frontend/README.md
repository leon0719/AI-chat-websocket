# AI Chat WebSocket Frontend

React 19 WebSocket 聊天機器人前端，支援即時 AI 串流回應。

## 技術棧

- **框架:** React 19 + TypeScript + Vite 7
- **樣式:** Tailwind CSS v4 + Radix UI / shadcn components
- **伺服器狀態:** TanStack React Query
- **客戶端狀態:** Zustand
- **表單處理:** React Hook Form + Zod
- **即時通訊:** WebSocket (In-Band JWT 認證)
- **Markdown 渲染:** react-markdown + remark-gfm + react-syntax-highlighter

## 快速開始

### 前置需求

- Node.js 18+ 或 Bun
- 後端服務運行中

### 安裝

```bash
# 安裝依賴
bun install

# 複製環境變數設定
cp .env.example .env

# 啟動開發伺服器
bun dev
```

開發伺服器預設運行於 http://localhost:5173

## 可用指令

| 指令 | 說明 |
|------|------|
| `bun dev` | 啟動開發伺服器 (Vite) |
| `bun build` | 建置生產版本 (tsc + vite) |
| `bun preview` | 預覽生產建置 |
| `bun format` | 使用 Biome 格式化程式碼 |
| `bun lint` | 使用 Biome 檢查程式碼 |
| `bun type-check` | TypeScript 型別檢查 |
| `bun check-exports` | 檢查未使用的 exports |

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `VITE_API_BASE_URL` | 後端 API URL | `http://localhost:8000/api` |
| `VITE_WS_BASE_URL` | WebSocket URL | `ws://localhost:8000` |

## 專案結構

```
src/
├── api/             # Axios client + API services
├── components/
│   ├── ui/          # shadcn/ui 基礎元件
│   ├── layout/      # 佈局元件
│   ├── auth/        # 認證表單
│   ├── chat/        # 聊天相關元件
│   └── common/      # 共用元件
├── hooks/
│   ├── queries/     # React Query hooks
│   └── useWebSocket.ts
├── stores/          # Zustand stores
├── types/           # TypeScript 型別定義
├── schemas/         # Zod 驗證 schemas
├── lib/             # 工具函式
├── pages/           # 頁面元件
└── routes/          # React Router 設定
```

## 功能特色

- **即時串流回應:** WebSocket 連線支援 AI 回應串流顯示
- **Markdown 支援:** AI 回應支援完整 Markdown 渲染，包含程式碼語法高亮
- **自動 Token 刷新:** Axios interceptor 自動處理 token 過期
- **React Compiler:** 自動 memoization 優化效能

## 認證流程

1. **登入:** API 回傳 access token，refresh token 存於 HttpOnly cookie
2. **Token 儲存:** Access token 僅存於 Zustand (記憶體)
3. **自動刷新:** 401 錯誤時自動刷新 token 並重試請求
4. **WebSocket 認證:** 連線後發送 `{"type": "auth", "token": "<jwt>"}` 訊息

## License

MIT
