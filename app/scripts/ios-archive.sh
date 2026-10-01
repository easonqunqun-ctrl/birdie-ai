#!/usr/bin/env bash
# 打 App Store Connect 用 IPA（组织 Team H5ZY5QNKRW）。
# 用法（在 app/ 目录）：
#   bash scripts/ios-archive.sh
#   UPLOAD=1 bash scripts/ios-archive.sh   # 打完用 ASC API Key 自动上传（同向野）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

flutter pub get
flutter build ipa \
  --release \
  --export-options-plist=ios/ExportOptions.plist \
  --dart-define=APP_ENV=production \
  --dart-define=API_BASE=https://api.birdieai.cn/v1 \
  --dart-define=MOCK_LOGIN=false

echo ""
echo "✓ IPA: $ROOT/build/ios/ipa/*.ipa"

if [[ "${UPLOAD:-0}" == "1" ]]; then
  bash "$ROOT/scripts/ios-upload.sh"
else
  echo "  上传：UPLOAD=1 bash scripts/ios-archive.sh"
  echo "  或：  bash scripts/ios-upload.sh"
fi
