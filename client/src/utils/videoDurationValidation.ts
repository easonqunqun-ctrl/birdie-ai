import { VIDEO_CONSTRAINTS } from '@/types/analysis'

/** 与 `ai_engine/app/pipeline/preprocess.py::MIN_DURATION_SEC` 对齐。 */
export const ENGINE_MIN_DURATION_SECONDS = 2.0

/**
 * 客户端上传门禁略高于引擎：微信 duration 常比 ffprobe 偏长（日志 2.0s → 1.7s）。
 */
export const CLIENT_MIN_DURATION_GATE_SECONDS = 2.3

export function validateVideoDurationForUpload(durationSec: number): string | null {
  if (!Number.isFinite(durationSec) || durationSec <= 0) {
    return '无法读取视频时长，请重新选择'
  }
  if (durationSec < CLIENT_MIN_DURATION_GATE_SECONDS) {
    return (
      `视频太短（${durationSec.toFixed(1)}s），请至少拍满 ` +
      `${VIDEO_CONSTRAINTS.MIN_DURATION_SECONDS} 秒（含完整上杆到收杆）`
    )
  }
  if (durationSec > VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS) {
    return (
      `视频太长（${durationSec.toFixed(1)}s），最多 ${VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS}s`
    )
  }
  return null
}

export function isVideoDurationOverLimit(durationSec: number): string | null {
  return validateVideoDurationForUpload(durationSec)
}
