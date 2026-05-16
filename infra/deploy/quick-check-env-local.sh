#!/usr/bin/env bash
# 快速自检 .env.local 是否仍带着「易被整段拷贝进运行时」的模板占位符。
# 用法（在 compose 工程根目录，与 docker-compose.yml / .env.local 同级）：
#   bash infra/deploy/quick-check-env-local.sh
#   bash infra/deploy/quick-check-env-local.sh /path/to/.env.local
set -euo pipefail

f="${1:-.env.local}"
if [[ ! -f "$f" ]]; then
  echo "✗ 未找到 $f （请先 cd 到实际跑 compose 的目录，例如 ~/lingniao-golf）"
  exit 1
fi

bad=0
# 只扫非注释、非空行，避免 `# 说明里出现 <change-me` 误判
hits="$(
  awk '!/^[[:space:]]*#/ && NF { print }' "$f" \
    | grep -niE '<change-me|<your-wx|<your-deepseek|<placeholder|<replace' || true
)"
if [[ -n "$hits" ]]; then
  echo "✗ 尖括号类占位:"
  echo "$hits"
  bad=1
fi

if grep -qiE '\.trycloudflare\.com|\.ngrok' "$f"; then
  echo "✗ 发现临时穿透域名（trycloudflare/ngrok）：公众平台无法配置 uploadFile。"
  bad=1
fi

if (( bad == 1 )); then
  echo ""
  echo "修复：编辑 $f 后执行（文件名按你实际 compose 对齐）："
  echo "  docker compose --env-file $f up -d --force-recreate backend celery-worker ai_engine"
  echo " （若叠加测试栈 nginx：再加 -f docker-compose.test.yml）"
  exit 1
fi

echo "✓ $f 未发现常见尖括号/穿透占位；若仍异常，核对 POSTGRES 与 DATABASE_URL、REDIS 与 REDIS_URL、MINIO ROOT 与 MINIO_* 密钥是否一致。"
exit 0
