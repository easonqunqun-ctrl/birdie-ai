.PHONY: help init up down restart logs ps clean reset \
        backend-shell backend-logs backend-test backend-lint backend-migrate backend-revision \
        backend-celery-logs backend-celery-shell \
        ai-shell ai-logs \
        client-install client-dev-weapp client-dev-rn-ios client-dev-rn-android client-build-weapp \
        check

# 默认目标：显示帮助
help:
	@echo "「小鸟 AI」开发命令清单"
	@echo ""
	@echo "  ===== 一键操作 ====="
	@echo "  make init              首次初始化（复制 .env、安装依赖）"
	@echo "  make up                启动全部服务（PostgreSQL+Redis+MinIO+Backend+AI）"
	@echo "  make down              停止全部服务"
	@echo "  make restart           重启全部服务"
	@echo "  make logs              查看实时日志"
	@echo "  make ps                查看服务状态"
	@echo "  make clean             清理容器（保留数据）"
	@echo "  make reset             清理容器和数据卷（彻底重置）"
	@echo ""
	@echo "  ===== 后端 ====="
	@echo "  make backend-shell     进入后端容器"
	@echo "  make backend-logs      查看后端日志"
	@echo "  make backend-test      运行后端测试"
	@echo "  make backend-lint      代码检查（ruff）"
	@echo "  make backend-migrate   执行数据库迁移"
	@echo "  make backend-revision m='msg'  生成新的迁移脚本"
	@echo "  make backend-celery-logs  查看 Celery worker 日志"
	@echo "  make backend-celery-shell 进入 Celery worker 容器"
	@echo ""
	@echo "  ===== AI 引擎 ====="
	@echo "  make ai-shell          进入 AI Engine 容器"
	@echo "  make ai-logs           查看 AI Engine 日志"
	@echo ""
	@echo "  ===== 客户端（Taro 双端） ====="
	@echo "  make client-install         安装客户端依赖"
	@echo "  make client-dev-weapp       开发：编译微信小程序（用 微信开发者工具 打开 client/dist）"
	@echo "  make client-dev-rn-ios      开发：iOS App"
	@echo "  make client-dev-rn-android  开发：Android App"
	@echo "  make client-build-weapp     生产：微信小程序构建"
	@echo ""
	@echo "  ===== 健康检查 ====="
	@echo "  make check             检查后端 /v1/health"

# ==================== 一键操作 ====================
init:
	@if [ ! -f .env.local ]; then \
		cp .env.example .env.local; \
		echo "✓ .env.local 已创建，请编辑填入真实配置"; \
	else \
		echo "✓ .env.local 已存在"; \
	fi
	@echo "提示：首次启动前请执行 make up"

up:
	docker compose --env-file .env.local up -d --build
	@echo ""
	@echo "✓ 服务已启动："
	@echo "  • Backend API:    http://localhost:8000/docs"
	@echo "  • AI Engine:      http://localhost:9100/docs"
	@echo "  • MinIO Console:  http://localhost:9001 (minioadmin/minioadmin)"
	@echo "  • PostgreSQL:     localhost:5432"
	@echo "  • Redis:          localhost:6379"

down:
	docker compose --env-file .env.local down

restart: down up

logs:
	docker compose --env-file .env.local logs -f --tail=100

ps:
	docker compose --env-file .env.local ps

clean:
	docker compose --env-file .env.local down --remove-orphans

reset:
	docker compose --env-file .env.local down -v --remove-orphans
	@echo "✓ 已清理所有容器和数据"

# ==================== 后端 ====================
backend-shell:
	docker compose --env-file .env.local exec backend sh

backend-logs:
	docker compose --env-file .env.local logs -f --tail=200 backend

backend-test:
	docker compose --env-file .env.local exec backend uv run pytest -v

backend-lint:
	docker compose --env-file .env.local exec backend uv run ruff check app/

backend-migrate:
	docker compose --env-file .env.local exec backend uv run alembic upgrade head

backend-revision:
	@if [ -z "$(m)" ]; then \
		echo "用法: make backend-revision m='your migration message'"; \
		exit 1; \
	fi
	docker compose --env-file .env.local exec backend uv run alembic revision --autogenerate -m "$(m)"

backend-celery-logs:
	docker compose --env-file .env.local logs -f --tail=200 celery-worker

backend-celery-shell:
	docker compose --env-file .env.local exec celery-worker sh

# ==================== AI 引擎 ====================
ai-shell:
	docker compose --env-file .env.local exec ai_engine sh

ai-logs:
	docker compose --env-file .env.local logs -f --tail=200 ai_engine

# ==================== 客户端 ====================
client-install:
	cd client && pnpm install

client-dev-weapp:
	cd client && pnpm dev:weapp

client-dev-rn-ios:
	cd client && pnpm dev:rn:ios

client-dev-rn-android:
	cd client && pnpm dev:rn:android

client-build-weapp:
	cd client && pnpm build:weapp

# ==================== 健康检查 ====================
check:
	@curl -s http://localhost:8000/v1/health | python3 -m json.tool || echo "✗ 后端未启动或异常"
