# Backend

FastAPI + SQLAlchemy + PostgreSQL 异步后端。

## 技术栈

- **Python 3.11**
- **FastAPI 0.115+**
- **SQLAlchemy 2 (asyncio)**
- **Pydantic v2** + pydantic-settings
- **Redis** + asyncpg
- **JWT** (python-jose)
- 包管理：**uv**（极快）

## 启动

整体启动（推荐）：根目录执行 `make up`。

单独本地启动（容器外）：

```bash
cd backend
uv sync
cp ../.env.example ../.env.local
# 改 .env.local 中的 POSTGRES_HOST / REDIS_HOST 为 localhost

# 启动一个本地 PostgreSQL + Redis（推荐还是用 docker-compose 起依赖）
docker compose -f ../docker-compose.yml --env-file ../.env.local up -d postgres redis

uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

访问：
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/v1/health>

## 测试登录链路（本地 mock 模式）

```bash
# 1. 健康检查
curl http://localhost:8000/v1/health

# 2. 用任意 code 模拟微信登录（mock 模式下会基于 code 哈希生成稳定 openid）
curl -X POST http://localhost:8000/v1/auth/wechat-login \
  -H "Content-Type: application/json" \
  -d '{"code": "test_code_001"}'

# 返回：{"code": 0, "message": "success", "data": {"token": "...", "user": {...}}}

# 3. 用 token 拉取自己的信息
TOKEN="<上面返回的 token>"
curl http://localhost:8000/v1/users/me -H "Authorization: Bearer $TOKEN"
```

## 目录

```
backend/
├── app/
│   ├── main.py              FastAPI 入口
│   ├── config.py            统一配置
│   ├── api/v1/              路由（auth/users/common）
│   ├── core/                基础设施（db/redis/security/middleware）
│   ├── models/              SQLAlchemy 模型
│   ├── schemas/             Pydantic 模型
│   ├── services/            业务逻辑
│   └── integrations/        第三方集成（微信/COS）
├── alembic/                 数据库迁移
└── pyproject.toml
```

## 开发命令

```bash
make backend-shell                          # 进容器
make backend-logs                           # 查看日志
make backend-migrate                        # 执行迁移
make backend-revision m="add foo column"    # 生成新迁移
make backend-test                           # 跑测试
make backend-lint                           # ruff 检查
```
