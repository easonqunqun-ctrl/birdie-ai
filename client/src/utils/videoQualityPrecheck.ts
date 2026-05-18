/**
 * O-08 子集：上传前客户端质量预检（启发式，非引擎真检）。
 * 机器码与 `ai_engine` / `qualityWarnings.ts` 对齐；无缩略图时 fail-open。
 */

export interface ThumbFrameMetrics {
  meanLuminance: number
  laplacianVariance: number
}

/** 与 `ai_engine/app/pipeline/preprocess.py` 软阈值同量级，按首帧缩略图缩放 */
export const CLIENT_PRECHECK_THRESHOLDS = {
  MEAN_LUMINANCE_LOW_LIGHT: 78,
  LAPLACIAN_VAR_VERY_BLURRY: 42,
  /** 对齐 `preprocess._WARN_LOW_STABILITY_BELOW` */
  STABILITY_SCORE_CAMERA_SHAKE: 0.42,
  /** 对齐 `preprocess._scan_quality`：mean_diff/30 → stability */
  STABILITY_MEAN_DIFF_SCALE: 30,
} as const

const SHAKE_SAMPLE_MAX_SIDE = 64

export interface VideoQualityPrecheckResult {
  warnings: string[]
  skipped?: boolean
  reason?: 'no_thumb' | 'unsupported_platform' | 'analysis_failed' | 'no_video_decoder'
  metrics?: ThumbFrameMetrics
  /** 视频前段多帧启发式稳像分 0–1（越大越稳） */
  shakeStabilityScore?: number
}

export function warningCodesFromThumbMetrics(m: ThumbFrameMetrics): string[] {
  const codes: string[] = []
  const dark =
    m.meanLuminance < CLIENT_PRECHECK_THRESHOLDS.MEAN_LUMINANCE_LOW_LIGHT ||
    (m.laplacianVariance < CLIENT_PRECHECK_THRESHOLDS.LAPLACIAN_VAR_VERY_BLURRY &&
      m.meanLuminance < 110)
  if (dark) codes.push('low_light')
  return codes
}

export function stabilityScoreFromMeanDiff(meanDiff: number): number {
  const scale = CLIENT_PRECHECK_THRESHOLDS.STABILITY_MEAN_DIFF_SCALE
  return Math.max(0, 1 - Math.min(meanDiff / scale, 1))
}

export function warningCodesFromStabilityScore(stabilityScore: number): string[] {
  if (stabilityScore < CLIENT_PRECHECK_THRESHOLDS.STABILITY_SCORE_CAMERA_SHAKE) {
    return ['camera_shake']
  }
  return []
}

export function mergeQualityWarningCodes(...groups: string[][]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const g of groups) {
    for (const c of g) {
      if (!seen.has(c)) {
        seen.add(c)
        out.push(c)
      }
    }
  }
  return out
}

/** 前段采样时刻（秒），避开挥杆中段大幅运动 */
export function earlyShakeSamplePositionsSec(durationSec: number): number[] {
  const d = Math.max(0.5, durationSec)
  const end = Math.min(1.2, d * 0.22)
  const count = 4
  if (count <= 1) return [0]
  return Array.from({ length: count }, (_, i) => (end * i) / (count - 1))
}

/** 最近邻缩放到固定尺寸灰度，供帧间 diff（与引擎 mean abs diff 同思路） */
export function downscaleRgbaToGray(
  data: Uint8ClampedArray | Uint8Array,
  srcW: number,
  srcH: number,
  dstW: number,
  dstH: number,
): Float32Array {
  const gray = new Float32Array(dstW * dstH)
  for (let dy = 0; dy < dstH; dy += 1) {
    for (let dx = 0; dx < dstW; dx += 1) {
      const sx = Math.min(srcW - 1, Math.floor((dx * srcW) / dstW))
      const sy = Math.min(srcH - 1, Math.floor((dy * srcH) / dstH))
      const o = (sy * srcW + sx) * 4
      gray[dy * dstW + dx] = 0.299 * data[o] + 0.587 * data[o + 1] + 0.114 * data[o + 2]
    }
  }
  return gray
}

export function meanAbsDiffGray(a: Float32Array, b: Float32Array): number {
  const n = Math.min(a.length, b.length)
  if (n === 0) return 0
  let sum = 0
  for (let i = 0; i < n; i += 1) sum += Math.abs(a[i] - b[i])
  return sum / n
}

/** 由连续灰度帧估计稳像分（与 `preprocess._scan_quality` 同源公式） */
export function stabilityScoreFromGrayFrames(frames: Float32Array[]): number | null {
  if (frames.length < 2) return null
  const diffs: number[] = []
  for (let i = 1; i < frames.length; i += 1) {
    diffs.push(meanAbsDiffGray(frames[i - 1], frames[i]))
  }
  const meanDiff = diffs.reduce((a, b) => a + b, 0) / diffs.length
  return stabilityScoreFromMeanDiff(meanDiff)
}

export function grayFromRgbaFrame(
  data: Uint8ClampedArray | Uint8Array,
  width: number,
  height: number,
): Float32Array {
  const side = SHAKE_SAMPLE_MAX_SIDE
  const scale = Math.min(1, side / Math.max(width, height, 1))
  const w = Math.max(8, Math.round(width * scale))
  const h = Math.max(8, Math.round(height * scale))
  return downscaleRgbaToGray(data, width, height, w, h)
}

/** 从 RGBA 像素（length = width * height * 4）计算亮度与拉普拉斯方差 */
export function metricsFromRgba(
  data: Uint8ClampedArray | Uint8Array,
  width: number,
  height: number,
): ThumbFrameMetrics {
  const n = width * height
  if (n === 0) {
    return { meanLuminance: 128, laplacianVariance: 200 }
  }

  const gray = new Float32Array(n)
  let lumSum = 0
  for (let i = 0; i < n; i += 1) {
    const o = i * 4
    const y = 0.299 * data[o] + 0.587 * data[o + 1] + 0.114 * data[o + 2]
    gray[i] = y
    lumSum += y
  }
  const meanLuminance = lumSum / n

  let lapSum = 0
  let lapSq = 0
  let lapCount = 0
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x
      const lap =
        -4 * gray[i] +
        gray[i - 1] +
        gray[i + 1] +
        gray[i - width] +
        gray[i + width]
      lapSum += lap
      lapSq += lap * lap
      lapCount += 1
    }
  }
  const laplacianVariance =
    lapCount > 0 ? Math.max(0, lapSq / lapCount - (lapSum / lapCount) ** 2) : 200

  return { meanLuminance, laplacianVariance }
}
