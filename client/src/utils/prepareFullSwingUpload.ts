/**
 * full_swing · params 页进入后后台上传 + detect-swings 的前置条件。
 * 纯逻辑便于单测；实际 IO 在 params.tsx 内调度。
 */

export type PrepareFullSwingPhase =
  | 'idle'
  | 'waiting_quality'
  | 'uploading'
  | 'detecting'
  | 'ready'
  | 'failed'

/** 后台 prepare 超过此时长后，提示用户可先选手动机位并提交。 */
export const PREPARE_BACKGROUND_HINT_TIMEOUT_MS = 5000

/** 是否应启动后台上传 + detect-swings（机位预选）。 */
export function shouldStartPrepareFullSwingUpload(input: {
  tempFilePath: string
  size: number
  duration: number
  analysisMode: string
  qualityChecking: boolean
  qualityBlockCount: number
}): boolean {
  if (!input.tempFilePath || !input.size || !input.duration) return false
  if (input.analysisMode !== 'full_swing') return false
  if (input.qualityChecking) return false
  if (input.qualityBlockCount > 0) return false
  return true
}

/** 后台 prepare 是否仍在进行（上传或机位识别）。 */
export function isPrepareInFlight(phase: PrepareFullSwingPhase): boolean {
  return phase === 'uploading' || phase === 'detecting'
}

/**
 * 提交按钮是否应等待后台 prepare 完成。
 * A：不再阻塞提交；用户可选手动机位后立即开始，提交时再 await 或走 fallback。
 */
export function shouldBlockSubmitWhilePreparing(_phase: PrepareFullSwingPhase): boolean {
  return false
}

/** 超时后是否展示「可先开始分析」慢路径提示。 */
export function shouldShowPrepareSlowPathHint(
  phase: PrepareFullSwingPhase,
  prepareSlowPathUnlocked: boolean,
): boolean {
  return isPrepareInFlight(phase) && prepareSlowPathUnlocked
}

/** params 页机位区后台 prepare 状态文案（分阶段 + 可选上传进度）。 */
export function prepareBackgroundStatusHint(
  phase: PrepareFullSwingPhase,
  uploadProgress: number | null,
  slowPathUnlocked: boolean,
): string | null {
  if (phase === 'uploading') {
    const pct =
      uploadProgress != null && uploadProgress > 0 ? ` ${uploadProgress}%` : ''
    const base = `正在后台上传视频${pct}…`
    if (slowPathUnlocked) {
      return `${base} 可先选球杆并点击「开始分析」。`
    }
    return base
  }
  if (phase === 'detecting') {
    const base = '正在识别拍摄机位…'
    if (slowPathUnlocked) {
      return `${base} 也可手动选择机位后直接开始分析。`
    }
    return `${base} 可先选球杆。`
  }
  return null
}

/** 是否可复用已完成的 prepare（跳过 handleStart 内二次上传）。 */
export function canReusePreparedUpload(phase: PrepareFullSwingPhase): boolean {
  return phase === 'ready'
}
