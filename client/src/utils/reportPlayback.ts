/**
 * 报告页视频播放源：原片 / 骨骼叠加切换（v1.2.4）。
 */

export type VideoPlaybackMode = 'original' | 'skeleton'

export function defaultPlaybackMode(report: {
  skeleton_video_url?: string | null
  video_url?: string | null
}): VideoPlaybackMode {
  return report.skeleton_video_url ? 'skeleton' : 'original'
}

export function canTogglePlaybackSource(report: {
  skeleton_video_url?: string | null
  video_url?: string | null
}): boolean {
  return Boolean(report.skeleton_video_url && report.video_url)
}

export function resolveReportPlaybackSrc(
  report: {
    skeleton_video_url?: string | null
    video_url?: string | null
  },
  mode: VideoPlaybackMode,
): string {
  if (mode === 'skeleton' && report.skeleton_video_url) {
    return report.skeleton_video_url
  }
  return report.video_url || ''
}
