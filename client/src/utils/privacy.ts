/**
 * 微信小程序隐私保护指引运行时封装
 *
 * 背景：
 *   微信官方 2023.9 起强制要求，涉及用户隐私的 API（wx.login / wx.chooseMedia
 *   / wx.getLocation 等）调用前必须先获得"隐私授权"；具体做法是在公众平台
 *   后台提交《小程序用户隐私保护指引》并审核通过，然后在代码侧挂以下 API：
 *     - `wx.getPrivacySetting(...)`       查询当前是否需要授权
 *     - `wx.requirePrivacyAuthorize(...)` 主动弹出授权弹窗
 *     - `wx.onNeedPrivacyAuthorization(...)` 隐私 API 被触发时的统一拦截
 *
 *   这些 API 要求基础库 ≥ 2.32.3，且只在微信小程序端存在。
 *   非 weapp 环境（H5 / RN / dev 构建）本封装会 no-op。
 *
 * 使用约定：
 *   1. **不要**在 App 里注册 `wx.onNeedPrivacyAuthorization` 后伪造 `resolve({ event: 'agree' })`：
 *      新基础库要求 `event: 'agree'` 时必须带用户真实点击过的 `buttonId`（见官方文档），
 *      否则真机/调试器内部校验可能抛 `Cannot convert undefined or null to object`。
 *   2. `ensurePrivacyAuthorized(apiName)` 在每次调用隐私 API 前 await：
 *      走 `getPrivacySetting` + `requirePrivacyAuthorize` 官方链路；用户拒绝 → 抛 PrivacyDeniedError
 *   3. 运行时若检测到基础库不支持这套 API（老版本微信），本封装静默放过，
 *      兜底 toast 已在 `app.tsx` 的最低基础库校验里统一处理
 */

/** 用户主动拒绝微信隐私授权时抛出 */
export class PrivacyDeniedError extends Error {
  constructor(public apiName: string) {
    super(`用户拒绝了隐私授权：${apiName}`)
    this.name = 'PrivacyDeniedError'
  }
}

/**
 * 当前环境是否支持微信隐私运行时 API。
 * 非小程序环境、或基础库 < 2.32.3 时返回 false。
 */
function isPrivacyApiSupported(): boolean {
  if (process.env.TARO_ENV !== 'weapp') return false
  const wxApi = typeof wx !== 'undefined' ? wx : undefined
  if (!wxApi) return false
  // 仅用于主动弹窗链路：getPrivacySetting + requirePrivacyAuthorize 即可。
  // 不要求 canIUse('onNeedPrivacyAuthorization')：部分基础库该项为 false 时
  // 仍可使用 requirePrivacyAuthorize；与「登录按钮 openType」方案并行不冲突。
  return !!(
    wxApi.canIUse?.('getPrivacySetting') &&
    wxApi.canIUse?.('requirePrivacyAuthorize')
  )
}

/**
 * 调用隐私 API（wx.login / chooseMedia 等）前的统一守卫。
 *
 * - 已授权或环境不支持：立即 resolve，调用方照常执行
 * - 未授权：弹微信官方授权弹窗；用户同意 → resolve；拒绝 → 抛 PrivacyDeniedError
 */
export async function ensurePrivacyAuthorized(apiName: string): Promise<void> {
  if (!isPrivacyApiSupported()) return

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wxApi: any = wx

  const setting: { needAuthorization?: boolean } = await new Promise((resolve, reject) => {
    wxApi.getPrivacySetting({
      success: resolve,
      fail: (err: { errMsg?: string }) => reject(new Error(err?.errMsg || 'getPrivacySetting failed')),
    })
  })

  if (!setting.needAuthorization) return

  await new Promise<void>((resolve, reject) => {
    wxApi.requirePrivacyAuthorize({
      success: () => resolve(),
      fail: () => reject(new PrivacyDeniedError(apiName)),
    })
  })
}

/**
 * 历史占位：曾在此注册 `wx.onNeedPrivacyAuthorization` 并直接 `resolve({ event: 'agree' })`，
 * 已不符合微信对 `buttonId` 的校验要求（真机易崩）。授权请只用 `ensurePrivacyAuthorized`。
 *
 * 若将来要做「全页自定义隐私弹窗」，需按官方示例：`button` 设 `open-type="agreePrivacyAuthorization"`
 * 与 `bindagreeprivacyauthorization`，在用户点击后再 `resolve({ buttonId, event: 'agree' })`。
 */
export function registerPrivacyAuthorizationHandler(): void {
  // 故意留空：不在此注册全局监听，避免非法 resolve 触发基础库内部异常。
}
