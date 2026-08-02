#!/usr/bin/env bash
# 打 App Store Connect 用 IPA（组织 Team H5ZY5QNKRW）。
# 用法（在 app/ 目录）：bash scripts/ios-archive.sh
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
echo "  用 Transporter 或 Xcode Organizer → Distribute 上传到 App Store Connect。"
