/** 格式化 PGC 时间锚点（毫秒 → m:ss） */

export function formatPgcTimeMarker(ms: number | null | undefined): string {
  if (ms == null) return '全程'
  const sec = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
