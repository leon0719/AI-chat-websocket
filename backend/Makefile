.PHONY: all format lint lint-fix type-check check test coverage clean unused help
.PHONY: install up down logs build rebuild
.PHONY: migrate makemigrations shell createsuperuser
.PHONY: docker-clean logs-api logs-db
.PHONY: prod-up prod-down prod-logs prod-build

# Docker compose files
COMPOSE_DEV = docker compose -f docker/docker-compose.dev.yml
COMPOSE_PROD = docker compose -f docker/docker-compose.prod.yml

# ===================
# Help
# ===================

help:
	@echo "========================================"
	@echo "  Django Ninja WebSocket Chatbot API"
	@echo "========================================"
	@echo ""
	@echo "開發環境 (Docker):"
	@echo "  make up                - 啟動開發容器 (日常開發用)"
	@echo "  make down              - 停止開發容器"
	@echo "  make build             - 僅建構開發映像 (不啟動)"
	@echo "  make rebuild           - 重新建構並啟動 (修改 Dockerfile 或 pyproject.toml 後使用)"
	@echo "  make logs              - 查看所有服務日誌"
	@echo "  make logs-api          - 查看 API 日誌"
	@echo "  make logs-db           - 查看資料庫日誌"
	@echo ""
	@echo "生產環境 (Docker):"
	@echo "  make prod-build        - 建構生產映像"
	@echo "  make prod-up           - 啟動生產容器"
	@echo "  make prod-down         - 停止生產容器"
	@echo "  make prod-logs         - 查看生產日誌"
	@echo ""
	@echo "Django 指令 (在開發容器中執行):"
	@echo "  make migrate           - 執行資料庫遷移"
	@echo "  make makemigrations    - 建立新遷移檔"
	@echo "  make shell             - 開啟 Django shell"
	@echo "  make createsuperuser   - 建立管理員帳號"
	@echo ""
	@echo "程式碼品質:"
	@echo "  make all               - 執行所有檢查 (format + lint + type-check)"
	@echo "  make format            - 格式化程式碼"
	@echo "  make lint              - 執行 ruff 檢查"
	@echo "  make type-check        - 執行 mypy 型別檢查"
	@echo "  make test              - 執行測試 (可用 TEST=\"path\" 指定測試)"
	@echo "  make coverage          - 執行測試並產生覆蓋率報告"
	@echo "  make unused            - 檢查未使用的函式"
	@echo ""
	@echo "其他:"
	@echo "  make install           - 安裝本地依賴 (僅供 IDE)"
	@echo "  make clean             - 清理快取檔案"
	@echo "  make docker-clean      - 清理開發環境 Docker 資料卷"

# ===================
# Local Setup (for IDE)
# ===================

install:
	uv sync

# ===================
# Development (Docker)
# ===================

up:
	$(COMPOSE_DEV) up -d
	@echo ""
	@echo "開發環境已啟動！"
	@echo "  API:      http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/api/docs"
	@echo ""
	@echo "首次啟動請執行:"
	@echo "  make migrate"
	@echo "  make createsuperuser"

down:
	$(COMPOSE_DEV) down

build:
	$(COMPOSE_DEV) build

rebuild:
	$(COMPOSE_DEV) up -d --build

logs:
	$(COMPOSE_DEV) logs -f

logs-api:
	$(COMPOSE_DEV) logs -f api

logs-db:
	$(COMPOSE_DEV) logs -f db

docker-clean:
	$(COMPOSE_DEV) down -v
	@echo "開發環境 Docker 資料卷已清理"

# ===================
# Production (Docker)
# ===================

prod-build:
	$(COMPOSE_PROD) build

prod-up:
	$(COMPOSE_PROD) up -d
	@echo ""
	@echo "生產環境已啟動！"
	@echo "  API: http://localhost:8000"

prod-down:
	$(COMPOSE_PROD) down

prod-logs:
	$(COMPOSE_PROD) logs -f

# ===================
# Django Commands (in dev container)
# ===================

migrate:
	$(COMPOSE_DEV) exec api uv run python manage.py migrate

makemigrations:
	$(COMPOSE_DEV) exec api uv run python manage.py makemigrations

shell:
	$(COMPOSE_DEV) exec api uv run python manage.py shell

createsuperuser:
	$(COMPOSE_DEV) exec api uv run python manage.py createsuperuser

# ===================
# Code Quality
# ===================

all:
	@echo "Running all code quality checks..."
	@echo ""
	@$(MAKE) format
	@echo ""
	@$(MAKE) lint
	@echo ""
	@$(MAKE) type-check
	@echo ""
	@$(MAKE) clean
	@echo "All checks completed!"

format:
	@echo "Formatting code with ruff..."
	@uv run ruff format .

lint:
	@echo "Linting code with ruff..."
	@uv run ruff check --fix .

type-check:
	@echo "Running type checks with mypy..."
	@uv run mypy .

test:
	@echo "Running tests..."
	@$(COMPOSE_DEV) exec api uv run pytest $(TEST)

coverage:
	@echo "Running tests with coverage..."
	@$(COMPOSE_DEV) exec api uv run pytest --cov=apps --cov-report=term-missing --cov-report=html $(TEST)
	@echo ""
	@echo "HTML 報告已產生至 htmlcov/ 目錄"

unused:
	@echo "Checking for unused functions..."
	@uv run python scripts/check_unused_functions.py

# ===================
# Cleanup
# ===================

clean:
	@echo "Cleaning cache files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf htmlcov .coverage 2>/dev/null || true
	@echo "Cache cleaned!"
