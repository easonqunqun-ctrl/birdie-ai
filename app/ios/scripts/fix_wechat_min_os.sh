#!/bin/sh
# WechatOpenSDK.framework Info.plist MinimumOSVersion=12.0，但二进制 LC_BUILD_VERSION minos=13.0，
# App Store 校验 90208。将 plist 对齐为 13.0 后必须重签，否则真机安装失败。
set -e
FW_DIR="${TARGET_BUILD_DIR}/${FRAMEWORKS_FOLDER_PATH}/WechatOpenSDK.framework"
FW="${FW_DIR}/Info.plist"
if [ ! -f "$FW" ]; then
  echo "note: WechatOpenSDK.framework Info.plist not found, skip"
  exit 0
fi

CURRENT=$(/usr/libexec/PlistBuddy -c 'Print :MinimumOSVersion' "$FW" 2>/dev/null || echo "")
if [ "$CURRENT" != "13.0" ]; then
  if [ -n "$CURRENT" ]; then
    /usr/libexec/PlistBuddy -c 'Set :MinimumOSVersion 13.0' "$FW"
  else
    /usr/libexec/PlistBuddy -c 'Add :MinimumOSVersion string 13.0' "$FW"
  fi
  echo "note: patched WechatOpenSDK MinimumOSVersion ${CURRENT:-missing} → 13.0"
else
  echo "note: WechatOpenSDK MinimumOSVersion already 13.0"
fi

# 只要改过 plist（含历史构建残留），都必须用当前签名身份重签
if [ -z "${EXPANDED_CODE_SIGN_IDENTITY:-}" ] || [ "${EXPANDED_CODE_SIGN_IDENTITY}" = "-" ]; then
  echo "warning: EXPANDED_CODE_SIGN_IDENTITY empty; skip re-sign"
  exit 0
fi
/usr/bin/codesign --force --sign "${EXPANDED_CODE_SIGN_IDENTITY}" \
  --preserve-metadata=identifier,entitlements,flags \
  --generate-entitlement-der \
  "${FW_DIR}"
echo "note: re-signed WechatOpenSDK.framework with ${EXPANDED_CODE_SIGN_IDENTITY}"
