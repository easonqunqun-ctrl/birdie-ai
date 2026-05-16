#!/usr/bin/env bash
# =====================================================
# W8 真机内测：本机内网穿透一键脚本（双隧道版）
# -----------------------------------------------------
# 同时管理两条 cloudflared 快速隧道：
#   1. backend  → http://localhost:8000   （API）
#   2. minio    → http://localhost:9000   （视频直传）
# 两条都必须暴露：
#   - API 给手机调登录 / 拉取报告 / 申请 upload-token
#   - MinIO 给手机走 wx.uploadFile 把视频 multipart POST 上来
#   后端签 presigned policy 时用 MINIO_PUBLIC_ENDPOINT，
#   所以 MINIO_PUBLIC_ENDPOINT 必须 = MinIO 隧道公网 URL，
#   否则手机上传时 400 / SignatureDoesNotMatch / 连不上。
#
# 协议固定 --protocol http2：QUIC 在国内 / 大文件场景断流严重。
#
# 用法：
#   ./scripts/dev_tunnel.sh start    # 起两条隧道 + 改 .env.local + 改 client/.env.test.local
#   ./scripts/dev_tunnel.sh stop     # 杀两条隧道
#   ./scripts/dev_tunnel.sh status   # 当前两条 URL + 健康
#   ./scripts/dev_tunnel.sh url      # 输出两条 URL
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$REPO_ROOT/.runtime"

# Backend 隧道
B_LOG="$RUNTIME_DIR/cloudflared.log"
B_PID="$RUNTIME_DIR/cloudflared.pid"
B_URL_FILE="$RUNTIME_DIR/cloudflared.url"
B_LOCAL="http://localhost:8000"

# MinIO 隧道
M_LOG="$RUNTIME_DIR/cloudflared-minio.log"
M_PID="$RUNTIME_DIR/cloudflared-minio.pid"
M_URL_FILE="$RUNTIME_DIR/cloudflared-minio.url"
M_LOCAL="http://localhost:9000"

ENV_LOCAL="$REPO_ROOT/.env.local"
CLIENT_ENV_FILE="$REPO_ROOT/client/.env.test.local"

mkdir -p "$RUNTIME_DIR"
cd "$REPO_ROOT"

CMD="${1:-start}"

cf_bin() {
    if command -v cloudflared >/dev/null 2>&1; then
        command -v cloudflared
    elif [[ -x /opt/homebrew/opt/cloudflared/bin/cloudflared ]]; then
        echo /opt/homebrew/opt/cloudflared/bin/cloudflared
    else
        echo "❌ cloudflared 未安装，请先：brew install cloudflared" >&2
        exit 1
    fi
}

stop_one() {
    local pid_file="$1"
    local match="$2"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
            echo "🛑 已杀 cloudflared (pid=$pid, match=$match)"
        fi
        rm -f "$pid_file"
    fi
    pkill -f "cloudflared.*--url $match" 2>/dev/null || true
}

stop_all() {
    stop_one "$B_PID" "$B_LOCAL"
    stop_one "$M_PID" "$M_LOCAL"
}

start_one() {
    # $1=local URL, $2=log file, $3=pid file, $4=url file, $5=label
    local local_url="$1" log="$2" pid_file="$3" url_file="$4" label="$5"
    local CF
    CF=$(cf_bin)
    : > "$log"
    nohup "$CF" tunnel --url "$local_url" --protocol http2 --no-autoupdate \
        > "$log" 2>&1 &
    echo $! > "$pid_file"
    local URL=""
    for _ in $(seq 1 30); do
        sleep 1
        URL=$(grep -Eo "https://[a-z0-9-]+\.trycloudflare\.com" "$log" \
              | head -1 || true)
        if [[ -n "$URL" ]]; then break; fi
    done
    if [[ -z "$URL" ]]; then
        echo "❌ [$label] 30s 内没拿到 URL，看日志：$log" >&2
        return 1
    fi
    echo "$URL" > "$url_file"
    echo "✅ [$label] $local_url  →  $URL"
}

sync_env_local() {
    # 同步 backend / MinIO 隧道 URL 进 .env.local
    #   - MINIO_PUBLIC_ENDPOINT 决定后端签 presigned policy / video / thumbnail 的对外域
    #   - API_PUBLIC_BASE_URL  决定 keyframe / SAMPLE_VIDEO_URL / SAMPLE_THUMBNAIL_URL
    #     被改写到的同源代理域；漏改会让真机收到死链 → 关键帧空白 / 示例视频 404
    local backend_url="$1" minio_url="$2"
    if [[ ! -f "$ENV_LOCAL" ]]; then
        echo "⚠️ $ENV_LOCAL 不存在，跳过同步" >&2
        return
    fi
    upsert_env() {
        local key="$1" val="$2"
        if grep -q "^${key}=" "$ENV_LOCAL"; then
            # macOS sed：用 | 作分隔符避免 URL 里 / 冲突
            sed -i '' "s|^${key}=.*|${key}=${val}|" "$ENV_LOCAL"
        else
            echo "${key}=${val}" >> "$ENV_LOCAL"
        fi
        echo "📝 .env.local → ${key}=${val}"
    }
    upsert_env "MINIO_PUBLIC_ENDPOINT" "$minio_url"
    upsert_env "API_PUBLIC_BASE_URL"  "$backend_url"
    upsert_env "SAMPLE_VIDEO_URL" \
        "${minio_url}/xiaoniao-videos/samples/swing_demo.mp4"
    upsert_env "SAMPLE_THUMBNAIL_URL" \
        "${minio_url}/xiaoniao-videos/samples/swing_demo_thumb.jpg"
}

sync_client_env() {
    # 把 TARO_APP_API_BASE_URL 改成 backend 隧道 URL/v1
    local backend_url="$1"
    local api_url="${backend_url}/v1"
    if [[ -f "$CLIENT_ENV_FILE" ]]; then
        if grep -q "^TARO_APP_API_BASE_URL=" "$CLIENT_ENV_FILE"; then
            sed -i '' "s|^TARO_APP_API_BASE_URL=.*|TARO_APP_API_BASE_URL=$api_url|" \
                "$CLIENT_ENV_FILE"
        else
            echo "TARO_APP_API_BASE_URL=$api_url" >> "$CLIENT_ENV_FILE"
        fi
    else
        cat > "$CLIENT_ENV_FILE" <<EOF
# 由 scripts/dev_tunnel.sh 自动维护，不要手动编辑 URL
TARO_APP_API_BASE_URL=$api_url
TARO_APP_ENV=test
TARO_APP_PAYMENT_MOCK=true
TARO_APP_PAYMENT_ENABLED=false
EOF
    fi
    echo "📝 client/.env.test.local → TARO_APP_API_BASE_URL=$api_url"
}

restart_backend() {
    if ! command -v docker >/dev/null 2>&1; then return; fi
    # ai_engine 也必须一起重启 —— 它在生成 skeleton_video_url 时用的是
    # 自己容器里的 MINIO_PUBLIC_ENDPOINT；不重启的话，新分析的报告页
    # 视频会指向旧 URL（http://localhost:9000）从而播不出。
    echo "🔄 重启 backend / celery-worker / ai_engine 容器以加载新 MINIO_PUBLIC_ENDPOINT..."
    COMPOSE_PROJECT_NAME=ai docker compose --env-file "$ENV_LOCAL" \
        up -d backend celery-worker ai_engine 2>&1 | tail -5 || true
}

start_tunnel() {
    stop_all
    start_one "$B_LOCAL" "$B_LOG" "$B_PID" "$B_URL_FILE" "backend" || exit 1
    start_one "$M_LOCAL" "$M_LOG" "$M_PID" "$M_URL_FILE" "minio  " || exit 1

    local B_URL M_URL
    B_URL=$(cat "$B_URL_FILE")
    M_URL=$(cat "$M_URL_FILE")

    sync_env_local "$B_URL" "$M_URL"
    sync_client_env "$B_URL"
    restart_backend

    echo
    echo "=================================================="
    echo "下一步：重编客户端，让 dist/ 里的 URL 也更新"
    echo "  cd client && rm -rf dist && pnpm build:weapp:test"
    echo
    echo "然后微信开发者工具 → 重新打开项目 → 真机调试 / 预览"
    echo "（项目设置里务必勾上：不校验合法域名 / TLS / HTTPS）"
    echo "=================================================="
}

case "$CMD" in
    start) start_tunnel ;;
    stop)  stop_all ;;
    url)
        echo "backend: $(cat "$B_URL_FILE" 2>/dev/null || echo '(no URL)')"
        echo "minio:   $(cat "$M_URL_FILE" 2>/dev/null || echo '(no URL)')"
        ;;
    status)
        for pair in "backend|$B_PID|$B_URL_FILE" "minio|$M_PID|$M_URL_FILE"; do
            label=$(echo "$pair" | cut -d'|' -f1)
            pidf=$(echo "$pair" | cut -d'|' -f2)
            urlf=$(echo "$pair" | cut -d'|' -f3)
            if [[ -f "$pidf" ]] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
                echo "🟢 [$label] running pid=$(cat "$pidf") url=$(cat "$urlf" 2>/dev/null || echo unknown)"
            else
                echo "🔴 [$label] not running"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {start|stop|status|url}" >&2
        exit 1 ;;
esac
