import {
  describeAnalysisFailure,
  type AnalysisFailureCopy,
} from '@/constants/analysisEngineErrors'
import { isRequestError } from '@/services/request'

/** params 页后台 detect-swings 失败快照（机位预选 / 提交前探测）。 */
export type DetectSwingsFailureInfo = AnalysisFailureCopy & {
  code: number | null
}

const DURATION_MESSAGE = /时长|不足\s*2|至少\s*2\s*秒/i

/** 50101 泛化码 + 时长文案 → 50106 专用提示（与日志「1.7s 不足 2.0s」对齐）。 */
export function normalizeDetectSwingsErrorCode(code: number, message: string): number {
  if (code === 50101 && DURATION_MESSAGE.test(message)) {
    return 50106
  }
  return code
}

export function resolveDetectSwingsFailure(err: unknown): DetectSwingsFailureInfo {
  if (isRequestError(err) && err.code != null && err.code >= 50101 && err.code <= 50123) {
    const message = (err.message || '').trim()
    const code = normalizeDetectSwingsErrorCode(err.code, message)
    return { ...describeAnalysisFailure({ code, message }), code }
  }

  const fallback = describeAnalysisFailure(null)
  return { ...fallback, code: null }
}

/** 机位预选失败且需重拍时，禁止提交（避免重复上传后同样失败）。 */
export function shouldBlockSubmitOnDetectPrepareFailure(
  failure: DetectSwingsFailureInfo | null,
): boolean {
  if (!failure?.code) return false
  if (failure.code === 50105) return false
  if (failure.code >= 50101 && failure.code <= 50123) {
    return failure.reshootRecommended
  }
  return false
}

export function detectPrepareFailureBannerLines(failure: DetectSwingsFailureInfo): string[] {
  const lines: string[] = [failure.message]
  if (failure.hint && failure.hint !== failure.message) {
    lines.push(failure.hint)
  }
  return lines
}
