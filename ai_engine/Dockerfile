# W6-T5：显式 pin 到 slim-bookworm（GLIBC 2.36），避免 python:3.11-slim tag
# 将来切到 trixie 时 mediapipe ABI 意外不兼容。bookworm 是 mediapipe 0.10.x
# wheel 的验证过的目标。
FROM python:3.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 系统依赖说明：
#   - curl:          uv 安装器 + download_samples.sh 拉视频
#   - ffmpeg:        W6-T1 视频转码（30fps / 720p / H.264 yuv420p）+ 合成异常视频
#   - libgl1:        opencv-python-headless 运行时依赖（libGL.so.1）
#   - libglib2.0-0:  opencv + mediapipe 运行时依赖
#   - build-essential: mediapipe wheel 对某些架构（比如 ARM）可能需要编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
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
