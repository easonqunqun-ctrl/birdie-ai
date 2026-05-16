#!/usr/bin/env bash
# CVM / 本地：若 .env 关闭微信支付 mock，则强制存在商户 PEM 的 compose overlay。
# 用法（仓库根）：
#   bash infra/deploy/check-cvm-pay-mount.sh
#   bash infra/deploy/check-cvm-pay-mount.sh /path/to/.env.local
# 退出码：0 = 无需检查或未关闭 mock；1 = 配置不满足真实支付部署要求。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

ENV_FILE="${1:-.env.local}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "⚠ 未找到 ${ENV_FILE}，跳过真实支付 compose 挂载检查"
  exit 0
fi

if ! grep -qE '^[[:space:]]*WECHAT_PAY_MOCK_MODE[[:space:]]*=[[:space:]]*(false|False|FALSE)' "${ENV_FILE}"; then
  exit 0
fi

if [[ ! -f docker-compose.wechat-pay-key.yml ]]; then
  echo "✗ ${ENV_FILE} 已设置 WECHAT_PAY_MOCK_MODE=false，但未找到 docker-compose.wechat-pay-key.yml" >&2
  echo "  解决：cp docker-compose.wechat-pay-key.example.yml docker-compose.wechat-pay-key.yml" >&2
  echo "  将 volumes 左侧改成服务器上 apiclient_key.pem 的绝对路径，再执行 make deploy-cvm-up。" >&2
  exit 1
fi

if ! grep -q 'apiclient_key.pem' docker-compose.wechat-pay-key.yml; then
  echo "✗ docker-compose.wechat-pay-key.yml 未引用 apiclient_key.pem（请检查 backend.volumes）" >&2
  exit 1
fi

echo "✓ 真实支付：已检测到 docker-compose.wechat-pay-key.yml（后端启动时仍会校验容器内 PEM 可读）"
