#!/usr/bin/env bash
# 把已打好的 IPA 传到 App Store Connect（与向野同一套 ASC API Key）。
# 密钥勿入库：~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8
# 环境变量：ASC_KEY_ID、ASC_ISSUER_ID（可写进 ~/.zshrc，勿提交 Git）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IPA="${1:-}"
if [[ -z "$IPA" ]]; then
  IPA="$(ls -1t "$ROOT"/build/ios/ipa/*.ipa 2>/dev/null | head -1 || true)"
fi
if [[ -z "$IPA" || ! -f "$IPA" ]]; then
  echo "✗ 找不到 IPA。先：cd app && bash scripts/ios-archive.sh" >&2
  exit 1
fi

KEY_ID="${ASC_KEY_ID:-}"
ISSUER="${ASC_ISSUER_ID:-}"
if [[ -z "$KEY_ID" || -z "$ISSUER" ]]; then
  echo "✗ 需要环境变量 ASC_KEY_ID 与 ASC_ISSUER_ID（向野同一套即可）" >&2
  exit 1
fi

KEYFILE="$HOME/.appstoreconnect/private_keys/AuthKey_${KEY_ID}.p8"
if [[ ! -f "$KEYFILE" ]]; then
  echo "✗ 缺少 $KEYFILE" >&2
  exit 1
fi

echo "→ 上传 $(basename "$IPA") 到 App Store Connect（ASC API Key）"
xcrun altool --upload-app --type ios --file "$IPA" \
  --apiKey "$KEY_ID" \
  --apiIssuer "$ISSUER"
echo "✓ 已提交上传。ASC → TestFlight 处理约 5–30 分钟。"
