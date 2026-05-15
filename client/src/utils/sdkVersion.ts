/**
 * 微信小程序基础库版本校验（W8-T2）
 *
 * 背景：
 *   W8 启用的若干 API（`wx.getPrivacySetting` 需 ≥ 2.32.3，
 *   `chooseMedia` 需 ≥ 2.10.0，`requestPayment` 需 ≥ 1.1.0）都有基础库门槛。
 *   项目侧我们取一条综合下限（`project.config.json::libVersion = "2.27.1"`），
 *   运行期检测到用户微信低于该版本 → toast 提示升级，避免白屏/静默失败。
 *
 * 使用：
 *   `App.componentDidMount` 里调用 `checkMinSdkVersion()` 一次即可。
 */

import Taro from '@tarojs/taro'

/** 与 `project.config.json::libVersion` 保持一致 */
export const MIN_SDK_VERSION = '2.27.1'

/**
 * 语义化版本比较（仅处理形如 `1.2.3` 的三段格式）。
 * @returns a > b → 1，a === b → 0，a < b → -1
 */
export function compareSemver(a: string, b: string): number {
  const pa = a.split('.').map((n) => parseInt(n, 10) || 0)
  const pb = b.split('.').map((n) => parseInt(n, 10) || 0)
  for (let i = 0; i < 3; i++) {
    const da = pa[i] ?? 0
    const db = pb[i] ?? 0
    if (da > db) return 1
    if (da < db) return -1
  }
  return 0
}

/**
 * 运行期校验当前微信基础库是否满足最低版本。
 * 不满足时 toast 提示升级；返回是否通过。
 * 非小程序环境（H5 / RN / dev）直接返回 true。
 */
export function checkMinSdkVersion(): boolean {
  if (process.env.TARO_ENV !== 'weapp') return true
  try {
    // 基础库 ≥ 2.20.1 起推荐 `getAppBaseInfo`；避免 `getSystemInfoSync` 弃用告警。
    // 老版本仍走 Taro → `wx.getSystemInfoSync`。
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const wxApi = typeof wx !== 'undefined' ? (wx as any) : undefined
    let sdk = ''
    if (wxApi?.canIUse?.('getAppBaseInfo')) {
      sdk = (wxApi.getAppBaseInfo?.() as { SDKVersion?: string })?.SDKVersion || ''
    } else {
      sdk = Taro.getSystemInfoSync().SDKVersion || ''
    }
    if (!sdk) return true
    if (compareSemver(sdk, MIN_SDK_VERSION) < 0) {
      Taro.showModal({
        title: '微信版本过低',
        content: `当前微信基础库 ${sdk}，部分功能将不可用，请升级微信到最新版本后再使用领翼golf。`,
        showCancel: false,
        confirmText: '我知道了'
      })
      return false
    }
    return true
  } catch {
    // 拿不到 SDKVersion 不阻塞主流程
    return true
  }
}
