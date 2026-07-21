/**
 * 安全区 inset。
 * 小程序：页面 SCSS 的 env(safe-area-*) 生效，这里返回 0，避免双重加垫。
 * （原 RN 分支已移除，App 端改用独立 Flutter 工程。）
 */

export type SafeAreaInsets = {
  top: number
  bottom: number
  left: number
  right: number
}

const ZERO: SafeAreaInsets = { top: 0, bottom: 0, left: 0, right: 0 }

export function getSafeAreaInsets(): SafeAreaInsets {
  return ZERO
}
