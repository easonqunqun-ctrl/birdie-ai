#!/usr/bin/env bash
# 规范化 CVM 后端滚动（默认针对 `docker-compose.yml` 里 `./backend:/app` 挂载时宿主机 `.venv` / `uv sync`）。
# `USE_DOCKER_COMPOSE_CVM_LAYER=1` 且存在 `docker-compose.cvm.yml` 时追加该层叠（无宿主 bind）。
#     此种情况请勿跑宿主机 venv：`FIX_HOST_BACKEND_VENV=0`（或跳过本脚本，直接 `make deploy-cvm-up`）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENVF="${ENV_FILE:-.env.local}"
COMPOSE_FILES=(-f docker-compose.yml)
if [[ -f docker-compose.test.yml ]] && [[ "${USE_TEST_COMPOSE:-1}" == "1" ]]; then
  COMPOSE_FILES+=(-f docker-compose.test.yml)
fi
if [[ -f docker-compose.cvm.yml ]] && [[ "${USE_DOCKER_COMPOSE_CVM_LAYER:-0}" == "1" ]]; then
  COMPOSE_FILES+=(-f docker-compose.cvm.yml)
fi

if [[ "${USE_DOCKER_COMPOSE_CVM_LAYER:-0}" == "1" ]]; then
  export FIX_HOST_BACKEND_VENV="${FIX_HOST_BACKEND_VENV:-0}"
  export SKIP_BACKEND_TREE_CHECK="${SKIP_BACKEND_TREE_CHECK:-1}"
fi

echo "=> 使用 env: $ENVF"

# Compose 挂载 ./backend:/app 时，宿主机 backend/.venv 会遮盖镜像内的依赖。
# rsync/Mac/半同步常见「坏 venv」→ ModuleNotFoundError: alembic.config。
FILES=(docker-compose.yml)
if [[ -f docker-compose.test.yml ]] && [[ "${USE_TEST_COMPOSE:-1}" == "1" ]]; then
  FILES+=(docker-compose.test.yml)
fi
BACKEND_MOUNTED=""
for f in "${FILES[@]}"; do
  if grep -Fq './backend:/app' "$ROOT/$f" 2>/dev/null; then
    BACKEND_MOUNTED="1"
    break
  fi
done

# 挂载 ./backend 时，Alembic 脚本必须在宿主机上存在（不完整 rsync 会缺 env.py → 502）
if [[ "${SKIP_BACKEND_TREE_CHECK:-0}" != "1" ]] && [[ -n "$BACKEND_MOUNTED" ]] \
  && [[ ! -f "$ROOT/backend/alembic/env.py" ]]; then
  echo "错误: $ROOT/backend/alembic/env.py 缺失。compose 使用 ./backend:/app 时必须同步完整仓库中的 backend/（含 alembic/）。" >&2
  echo "在 CVM: git pull --ff-only（或 rsync 整个 backend/），勿只同步 app。" >&2
  exit 1
fi

if [[ "${FIX_HOST_BACKEND_VENV:-1}" == "1" ]] && [[ -n "$BACKEND_MOUNTED" ]]; then
  echo "=> 检测到 backend 挂载 ./backend:/app，确保宿主机 venv 与 Linux 镜像一致..."
  VENVD="$ROOT/backend/.venv"
  if [[ -e "$VENVD" ]]; then
    echo "=> 移除宿主机 backend/.venv..."
    if ! rm -rf "$VENVD" 2>/dev/null; then
      echo "=> 普通用户无法删除（常为容器 root 写入绑定挂载）；使用 sudo ..."
      sudo rm -rf "$VENVD"
    fi
  fi
  echo "=> 在本机挂载目录 uv sync（需拉 PyPI wheel；容器内仍为 root）..."
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENVF" stop backend celery-worker 2>/dev/null || true
  docker compose "${COMPOSE_FILES[@]}" --env-file "$ENVF" run --rm --no-deps backend \
    sh -lc 'cd /app && uv sync'
  if [[ -d "$VENVD" ]]; then
    OWNER="$(stat -c '%u:%g' "$ROOT/backend" 2>/dev/null || echo '1000:1000')"
    CUR="$(stat -c '%u:%g' "$VENVD" 2>/dev/null || echo '')"
    if [[ "$CUR" != "$OWNER" ]]; then
      echo "=> 将 backend/.venv 属主设为与 backend/ 目录一致 (${OWNER})，避免下次无法用 rm 清除..."
      sudo chown -R "$OWNER" "$VENVD"
    fi
  fi
fi

docker compose "${COMPOSE_FILES[@]}" --env-file "$ENVF" build backend celery-worker
docker compose "${COMPOSE_FILES[@]}" --env-file "$ENVF" up -d --force-recreate backend celery-worker
if docker ps --format '{{.Names}}' | grep -qx 'xiaoniao-nginx'; then
  docker restart xiaoniao-nginx || true
fi
echo "=> 完成。可 curl -sk https://你的API/v1/health"
