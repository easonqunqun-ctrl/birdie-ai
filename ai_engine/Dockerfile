FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY uv.lock* ./
# pyproject.toml 声明了 readme = "README.md"，uv 做 editable self-install 时会读取它，
# 因此必须与 pyproject 一起先 COPY 进来，避免 hatchling 构建报 "Readme file does not exist"。
COPY README.md ./

RUN uv sync --frozen 2>/dev/null || uv sync

COPY . .

EXPOSE 9000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
