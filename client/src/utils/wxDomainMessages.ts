/**
 * 微信小程序「合法域名」类错误统一文案。
 * wx.request / wx.uploadFile / wx.downloadFile 在真机上都会校验服务器域名，
 * errMsg 英/中混排，抽到一处便于产品与运维对照后台配置。
 */

function safeHostname(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return ''
  }
}

function isWxDomainListError(raw: string): boolean {
  const lower = raw.trim().toLowerCase()
  return (
    lower.includes('not in domain list') ||
    lower.includes('domain list') ||
    raw.includes('合法域名')
  )
}

/**
 * @param apiName 与公众平台「服务器域名」中的配置项一致。
 */
export function formatWxDomainComplianceError(
  apiName: 'request' | 'uploadFile' | 'downloadFile',
  rawErrMsg: string,
  attemptedUrl?: string,
): string {
  const raw = rawErrMsg.trim()
  if (!raw) return '网络异常，请稍后重试'
  if (!isWxDomainListError(raw)) return raw.length > 80 ? `${raw.slice(0, 79)}…` : raw

  const host = attemptedUrl ? safeHostname(attemptedUrl) : ''
  const portal =
    apiName === 'request'
      ? 'request 合法域名'
      : apiName === 'uploadFile'
        ? 'uploadFile 合法域名'
        : 'downloadFile 合法域名'

  if (host === 'localhost' || host === '127.0.0.1') {
    return (
      `当前地址为本机（${host}），真机/体验版不可用。` +
      `请改用 HTTPS 线上域名（如 TARO_APP_API_BASE_URL）并重新编译。`
    )
  }
  if (host) {
    return `请在公众平台「服务器域名→${portal}」添加：https://${host}` +
      `（须与实际请求的 https 主机一致；不要带路径）`
  }
  return `请在公众平台配置「${portal}」；修改后台后需在开发者工具中刷新域名信息并重编小程序。`
}
