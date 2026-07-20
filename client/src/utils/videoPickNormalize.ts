/**
 * 选片 / 拍摄后的纯函数规范化（weapp + RN 共用，便于单测）。
 */

import { VIDEO_CONSTRAINTS } from '@/types/analysis'
import { validateVideoDurationForUpload } from '@/utils/videoDurationValidation'

/** App 拍摄预设（SP-1 / SP-2）；高帧率原生模块未接入前均为 best-effort */
export type CapturePresetId = 'standard' | 'high_quality'

export const CAPTURE_PRESET_LABEL: Record<CapturePresetId, string> = {
  standard: '标准高清',
  high_quality: '高质量（帧率以系统相机能力为准）',
}

/** iOS image-picker 常见毫秒；Android / weapp 多为秒 */
export function normalizePickerDurationSeconds(durationRaw: number): number {
  if (!Number.isFinite(durationRaw) || durationRaw <= 0) return 0
  return durationRaw > 1000 ? durationRaw / 1000 : durationRaw
}

/** 去掉 query；从路径取扩展名（小写，无点） */
export function extractVideoExt(path: string): string {
  const clean = String(path || '').split('?')[0]
  const dotIdx = clean.lastIndexOf('.')
  if (dotIdx === -1) return ''
  return clean.slice(dotIdx + 1).toLowerCase()
}

/**
 * RN 本地 URI：保证 file:// 前缀（content:// / ph:// 保持原样，交给原生上传）。
 */
export function normalizeLocalVideoUri(uri: string): string {
  const u = String(uri || '').trim()
  if (!u) return u
  if (/^(file|content|ph|assets-library|http|https):/i.test(u)) return u
  if (u.startsWith('/')) return `file://${u}`
  return u
}

export function formatVideoBytes(bytes: number): string {
  if (!bytes || bytes < 0) return '-'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

export interface PickedVideoForValidation {
  size: number
  duration: number
  filePath: string
}

/** 返回 null 表示合规；否则为面向用户的错误文案 */
export function validatePickedVideo(v: PickedVideoForValidation): string | null {
  const { MAX_SIZE_BYTES, ACCEPTED_EXTENSIONS } = VIDEO_CONSTRAINTS
  const durationErr = validateVideoDurationForUpload(v.duration)
  if (durationErr) return durationErr
  if (v.size > MAX_SIZE_BYTES) {
    return `文件过大（${formatVideoBytes(v.size)}），限 ${Math.round(MAX_SIZE_BYTES / 1024 / 1024)}MB 以内`
  }
  const ext = extractVideoExt(v.filePath)
  // 相册 / content URI 常无扩展名：放行，由后端兜底
  if (ext && !ACCEPTED_EXTENSIONS.includes(ext as (typeof ACCEPTED_EXTENSIONS)[number])) {
    return `暂不支持 .${ext} 格式，请选择 ${ACCEPTED_EXTENSIONS.join('/').toUpperCase()}`
  }
  return null
}

/** SP-1 对照记录用的一行摘要（可复制到结果表备注） */
export function formatVideoPickSummary(meta: {
  source: string
  preset?: CapturePresetId
  width: number
  height: number
  duration: number
  size: number
  filePath: string
}): string {
  const res =
    meta.width > 0 && meta.height > 0 ? `${meta.width}×${meta.height}` : '分辨率未知'
  const preset = meta.preset ? CAPTURE_PRESET_LABEL[meta.preset] : '-'
  const ext = extractVideoExt(meta.filePath) || '未知格式'
  return [
    `source=${meta.source}`,
    `preset=${preset}`,
    res,
    `${meta.duration.toFixed(2)}s`,
    formatVideoBytes(meta.size),
    ext,
  ].join(' · ')
}
