FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（极快的 Python 包管理器）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# 先复制依赖描述文件，利用 docker 缓存
COPY pyproject.toml ./
COPY uv.lock* ./
# pyproject.toml 声明了 readme = "README.md"，uv 做 editable self-install 时会读取它，
# 因此必须与 pyproject 一起先 COPY 进来，避免 hatchling 构建报 "Readme file does not exist"。
COPY README.md ./

# 安装依赖
RUN uv sync --frozen 2>/dev/null || uv sync

# 复制源码
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
