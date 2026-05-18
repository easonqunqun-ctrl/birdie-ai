import Taro from '@tarojs/taro'
import {
  earlyShakeSamplePositionsSec,
  grayFromRgbaFrame,
  mergeQualityWarningCodes,
  metricsFromRgba,
  stabilityScoreFromGrayFrames,
  warningCodesFromStabilityScore,
  warningCodesFromThumbMetrics,
  type VideoQualityPrecheckResult,
} from '@/utils/videoQualityPrecheck'

const SAMPLE_MAX_SIDE = 128
const DECODER_START_MS = 12_000
const DECODER_SEEK_MS = 2_500
const SHAKE_ANALYSIS_MS = 5_000

interface DecodedFrame {
  data: Uint8ClampedArray
  width: number
  height: number
}

interface WxVideoDecoder {
  start(options: { source: string; mode?: number }): void
  seek(position: number): void
  stop(): void
  getFrameData(): { width: number; height: number; data: ArrayBuffer } | null
  on(event: string, listener: (...args: unknown[]) => void): void
  off(event: string, listener: (...args: unknown[]) => void): void
}

function getVideoDecoderFactory(): (() => WxVideoDecoder) | null {
  const g = globalThis as { wx?: { createVideoDecoder?: () => WxVideoDecoder } }
  if (typeof g.wx?.createVideoDecoder === 'function') {
    return g.wx.createVideoDecoder.bind(g.wx)
  }
  return null
}

async function analyzeThumbPath(thumbPath: string): Promise<{
  warnings: string[]
  metrics: ReturnType<typeof metricsFromRgba>
} | null> {
  const info = await Taro.getImageInfo({ src: thumbPath })
  const scale = Math.min(1, SAMPLE_MAX_SIDE / Math.max(info.width, info.height, 1))
  const w = Math.max(8, Math.round(info.width * scale))
  const h = Math.max(8, Math.round(info.height * scale))

  if (typeof Taro.createOffscreenCanvas !== 'function') {
    return null
  }

  const canvas = Taro.createOffscreenCanvas({ type: '2d', width: w, height: h })
  const ctx = canvas.getContext('2d') as CanvasRenderingContext2D | null
  if (!ctx) return null

  const img = canvas.createImage() as HTMLImageElement
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('thumb load failed'))
    img.src = thumbPath
  })
  ctx.drawImage(img, 0, 0, w, h)
  const imageData = ctx.getImageData(0, 0, w, h)
  const metrics = metricsFromRgba(imageData.data, w, h)
  return { warnings: warningCodesFromThumbMetrics(metrics), metrics }
}

function startDecoder(decoder: WxVideoDecoder, source: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('decoder start timeout')), DECODER_START_MS)
    const onStart = () => {
      clearTimeout(timer)
      decoder.off('start', onStart)
      decoder.off('error', onError)
      resolve()
    }
    const onError = (err: unknown) => {
      clearTimeout(timer)
      decoder.off('start', onStart)
      decoder.off('error', onError)
      reject(err instanceof Error ? err : new Error('decoder error'))
    }
    decoder.on('start', onStart)
    decoder.on('error', onError)
    decoder.start({ source, mode: 0 })
  })
}

function decodeFrameAt(decoder: WxVideoDecoder, positionSec: number): Promise<DecodedFrame | null> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      decoder.off('seek', onSeek)
      resolve(null)
    }, DECODER_SEEK_MS)

    const onSeek = () => {
      clearTimeout(timer)
      decoder.off('seek', onSeek)
      try {
        const raw = decoder.getFrameData()
        if (!raw?.data || raw.width <= 0 || raw.height <= 0) {
          resolve(null)
          return
        }
        resolve({
          data: new Uint8ClampedArray(raw.data),
          width: raw.width,
          height: raw.height,
        })
      } catch {
        resolve(null)
      }
    }
    decoder.on('seek', onSeek)
    decoder.seek(positionSec)
  })
}

async function sampleEarlyGrayFrames(
  videoPath: string,
  durationSec: number,
): Promise<Float32Array[]> {
  const createDecoder = getVideoDecoderFactory()
  if (!createDecoder || !videoPath.trim() || durationSec <= 0) {
    return []
  }

  const decoder = createDecoder()
  const positions = earlyShakeSamplePositionsSec(durationSec)
  const grays: Float32Array[] = []

  try {
    await startDecoder(decoder, videoPath)
    for (const pos of positions) {
      const frame = await decodeFrameAt(decoder, pos)
      if (frame) {
        grays.push(grayFromRgbaFrame(frame.data, frame.width, frame.height))
      }
    }
  } finally {
    try {
      decoder.stop()
    } catch {
      /* ignore */
    }
  }

  return grays
}

async function analyzeVideoShake(
  videoPath: string,
  durationSec: number,
): Promise<{ stabilityScore: number | null; warnings: string[] }> {
  const grays = await sampleEarlyGrayFrames(videoPath, durationSec)
  const stabilityScore = stabilityScoreFromGrayFrames(grays)
  if (stabilityScore == null) {
    return { stabilityScore: null, warnings: [] }
  }
  return {
    stabilityScore,
    warnings: warningCodesFromStabilityScore(stabilityScore),
  }
}

function withShakeTimeout<T>(p: Promise<T>): Promise<T | null> {
  return Promise.race([
    p,
    new Promise<null>((resolve) => {
      setTimeout(() => resolve(null), SHAKE_ANALYSIS_MS)
    }),
  ])
}

export async function precheckVideoQualityWeapp(input: {
  thumbTempFilePath?: string
  videoTempFilePath?: string
  durationSec?: number
}): Promise<VideoQualityPrecheckResult> {
  const thumbPath = input.thumbTempFilePath?.trim() || ''
  const videoPath = input.videoTempFilePath?.trim() || ''
  const durationSec = input.durationSec ?? 0

  let thumbWarnings: string[] = []
  let metrics: VideoQualityPrecheckResult['metrics']

  if (thumbPath) {
    try {
      const thumb = await analyzeThumbPath(thumbPath)
      if (thumb) {
        thumbWarnings = thumb.warnings
        metrics = thumb.metrics
      }
    } catch {
      /* thumb fail-open */
    }
  }

  let shakeWarnings: string[] = []
  let shakeStabilityScore: number | undefined
  let shakeSkippedReason: VideoQualityPrecheckResult['reason']

  if (videoPath && durationSec > 0) {
    if (!getVideoDecoderFactory()) {
      shakeSkippedReason = 'no_video_decoder'
    } else {
      const shakeResult = await withShakeTimeout(analyzeVideoShake(videoPath, durationSec))
      if (shakeResult === null) {
        shakeSkippedReason = 'analysis_failed'
      } else {
        shakeWarnings = shakeResult.warnings
        if (shakeResult.stabilityScore != null) {
          shakeStabilityScore = shakeResult.stabilityScore
        }
      }
    }
  }

  const warnings = mergeQualityWarningCodes(thumbWarnings, shakeWarnings)

  if (!thumbPath && !videoPath) {
    return { warnings: [], skipped: true, reason: 'no_thumb' }
  }

  return {
    warnings,
    metrics,
    shakeStabilityScore,
    skipped: warnings.length === 0 && !!shakeSkippedReason && !thumbPath,
    reason:
      shakeSkippedReason ||
      (!thumbPath && !videoPath ? 'no_thumb' : undefined),
  }
}
