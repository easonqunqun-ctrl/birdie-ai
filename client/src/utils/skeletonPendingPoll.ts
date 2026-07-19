/**
 * 报告页：骨骼异步补渲染时的短轮询控制（与 React effect 解耦，便于单测）。
 */

export const SKELETON_POLL_INTERVAL_MS = 2500
export const SKELETON_POLL_MAX_TRIES = 12

export function shouldPollSkeletonPending(report: {
  skeleton_video_url?: string | null
  engine_warnings?: Array<{ code?: string } | null> | null
} | null | undefined): boolean {
  if (!report) return false
  if (report.skeleton_video_url) return false
  return (report.engine_warnings || []).some((w) => w?.code === 'skeleton_pending')
}

/** 是否在拿到新报告后继续下一轮轮询。 */
export function shouldContinueSkeletonPoll(
  report: {
    skeleton_video_url?: string | null
    engine_warnings?: Array<{ code?: string } | null> | null
  },
  tries: number,
  maxTries: number = SKELETON_POLL_MAX_TRIES,
): boolean {
  if (tries >= maxTries) return false
  return shouldPollSkeletonPending(report)
}
