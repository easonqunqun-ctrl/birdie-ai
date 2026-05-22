/**
 * O-08 子集：上传前客户端质量预检（启发式，非引擎真检）。
 * v1.2.0：5s 硬超时 + 阻断/警告分级（对齐 preprocess 硬/软阈值量级）。
 */

/** 与 docs/01 §4.4「5 秒内完成」对齐；超时 fail-open，不阻断上传 */
export const PRECHECK_HARD_TIMEOUT_MS = 5000

export interface ThumbFrameMetrics {
  meanLuminance: number
  laplacianVariance: number
}

/** 与 `ai_engine/app/pipeline/preprocess.py` 硬/软阈值同量级，按首帧缩略图缩放 */
export const CLIENT_PRECHECK_THRESHOLDS = {
  MEAN_LUMINANCE_BLOCK: 35,
  LAPLACIAN_VAR_BLOCK: 18,
  STABILITY_SCORE_BLOCK: 0.18,
  MEAN_LUMINANCE_LOW_LIGHT: 78,
  LAPLACIAN_VAR_VERY_BLURRY: 42,
  STABILITY_SCORE_CAMERA_SHAKE: 0.42,
  STABILITY_MEAN_DIFF_SCALE: 30,
} as const

const SHAKE_SAMPLE_MAX_SIDE = 64

export interface VideoQualityPrecheckResult {
  warnings: string[]
  blocks: string[]
  skipped?: boolean
  reason?:
    | 'no_thumb'
    | 'unsupported_platform'
    | 'analysis_failed'
    | 'no_video_decoder'
    | 'timeout'
  timedOut?: boolean
  elapsedMs?: number
  metrics?: ThumbFrameMetrics
  shakeStabilityScore?: number
}

export function blockingCodesFromThumbMetrics(m: ThumbFrameMetrics): string[] {
  if (m.meanLuminance < CLIENT_PRECHECK_THRESHOLDS.MEAN_LUMINANCE_BLOCK) {
    return ['too_dark']
  }
  if (
    m.laplacianVariance < CLIENT_PRECHECK_THRESHOLDS.LAPLACIAN_VAR_BLOCK &&
    m.meanLuminance < 90
  ) {
    return ['too_blurry']
  }
  return []
}

export function blockingCodesFromStabilityScore(stabilityScore: number): string[] {
  if (stabilityScore < CLIENT_PRECHECK_THRESHOLDS.STABILITY_SCORE_BLOCK) {
    return ['too_shaky']
  }
  return []
}

export function warningCodesFromThumbMetrics(m: ThumbFrameMetrics): string[] {
  if (blockingCodesFromThumbMetrics(m).length > 0) return []
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
  if (blockingCodesFromStabilityScore(stabilityScore).length > 0) return []
  if (stabilityScore < CLIENT_PRECHECK_THRESHOLDS.STABILITY_SCORE_CAMERA_SHAKE) {
    return ['camera_shake']
  }
  return []
}

/** 汇总 thumb + shake 为 blocks / warnings 两档（互斥：已阻断不再给软警告） */
export function classifyVideoQualityPrecheck(input: {
  thumbMetrics?: ThumbFrameMetrics
  shakeStabilityScore?: number | null
}): { blocks: string[]; warnings: string[] } {
  const blockGroups: string[][] = []
  const warnGroups: string[][] = []

  if (input.thumbMetrics) {
    blockGroups.push(blockingCodesFromThumbMetrics(input.thumbMetrics))
    warnGroups.push(warningCodesFromThumbMetrics(input.thumbMetrics))
  }
  if (input.shakeStabilityScore != null) {
    blockGroups.push(blockingCodesFromStabilityScore(input.shakeStabilityScore))
    warnGroups.push(warningCodesFromStabilityScore(input.shakeStabilityScore))
  }

  const blocks = mergeQualityWarningCodes(...blockGroups)
  const warnings =
    blocks.length > 0 ? [] : mergeQualityWarningCodes(...warnGroups)
  return { blocks, warnings }
}

export async function withPrecheckTimeout<T>(
  task: Promise<T>,
  timeoutMs: number = PRECHECK_HARD_TIMEOUT_MS,
): Promise<{ result: T | null; timedOut: boolean }> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      task.then((result) => ({ result, timedOut: false as const })),
      new Promise<{ result: null; timedOut: true }>((resolve) => {
        timer = setTimeout(() => resolve({ result: null, timedOut: true }), timeoutMs)
      }),
    ])
  } finally {
    if (timer) clearTimeout(timer)
  }
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
