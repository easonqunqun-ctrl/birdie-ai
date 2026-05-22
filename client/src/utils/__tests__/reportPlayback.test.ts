import {
  canTogglePlaybackSource,
  defaultPlaybackMode,
  resolveReportPlaybackSrc,
} from '@/utils/reportPlayback'

describe('reportPlayback', () => {
  const report = {
    video_url: 'https://api.example/v/original.mp4',
    skeleton_video_url: 'https://api.example/v/skeleton.mp4',
  }

  test('defaultPlaybackMode prefers skeleton when available', () => {
    expect(defaultPlaybackMode(report)).toBe('skeleton')
    expect(defaultPlaybackMode({ video_url: report.video_url })).toBe('original')
  })

  test('canTogglePlaybackSource requires both URLs', () => {
    expect(canTogglePlaybackSource(report)).toBe(true)
    expect(canTogglePlaybackSource({ video_url: report.video_url })).toBe(false)
  })

  test('resolveReportPlaybackSrc switches by mode', () => {
    expect(resolveReportPlaybackSrc(report, 'skeleton')).toBe(report.skeleton_video_url)
    expect(resolveReportPlaybackSrc(report, 'original')).toBe(report.video_url)
  })
})
