/**
 * 同源资源 URL：小程序 `<Video>` / `<Image>` 仅允许已登记 HTTPS 域名。
 * 练习示范、示例报告等静态素材走 `{API}/v1/assets/{video|image}/{key}`。
 */

declare const API_BASE_URL: string

function apiBase(): string {
  const raw = typeof API_BASE_URL === 'string' ? API_BASE_URL.trim() : ''
  return raw.replace(/\/$/, '')
}

export function buildAssetVideoUrl(key: string): string {
  const normalized = key.replace(/^\//, '')
  return `${apiBase()}/assets/video/${normalized}`
}

export function buildAssetImageUrl(key: string): string {
  const normalized = key.replace(/^\//, '')
  return `${apiBase()}/assets/image/${normalized}`
}
