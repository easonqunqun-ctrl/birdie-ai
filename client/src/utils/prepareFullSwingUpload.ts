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

/** 提交按钮是否应等待后台 prepare 完成（避免重复上传 / 竞态）。 */
export function shouldBlockSubmitWhilePreparing(phase: PrepareFullSwingPhase): boolean {
  return phase === 'uploading' || phase === 'detecting'
}

/** 是否可复用已完成的 prepare（跳过 handleStart 内二次上传）。 */
export function canReusePreparedUpload(phase: PrepareFullSwingPhase): boolean {
  return phase === 'ready'
}
