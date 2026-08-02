#!/bin/sh
# WechatOpenSDK.framework Info.plist MinimumOSVersion=12.0，但二进制 LC_BUILD_VERSION minos=13.0，
# App Store 校验 90208。将 plist 对齐为 13.0（与 Runner IPHONEOS_DEPLOYMENT_TARGET 一致）。
set -e
FW="${TARGET_BUILD_DIR}/${FRAMEWORKS_FOLDER_PATH}/WechatOpenSDK.framework/Info.plist"
if [ ! -f "$FW" ]; then
  echo "note: WechatOpenSDK.framework Info.plist not found, skip"
  exit 0
fi
CURRENT=$(/usr/libexec/PlistBuddy -c 'Print :MinimumOSVersion' "$FW" 2>/dev/null || echo "")
if [ "$CURRENT" = "13.0" ]; then
  echo "note: WechatOpenSDK MinimumOSVersion already 13.0"
  exit 0
fi
if [ -n "$CURRENT" ]; then
  /usr/libexec/PlistBuddy -c 'Set :MinimumOSVersion 13.0' "$FW"
else
  /usr/libexec/PlistBuddy -c 'Add :MinimumOSVersion string 13.0' "$FW"
fi
echo "note: patched WechatOpenSDK MinimumOSVersion ${CURRENT:-missing} → 13.0"
