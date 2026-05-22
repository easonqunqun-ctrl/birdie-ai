import {
  getDrillVideoDetail,
  resolveVideoCardDetail,
} from '@/constants/drillVideoLibrary'

describe('drillVideoLibrary', () => {
  it('三大 heuristic drill 均有视频', () => {
    for (const id of ['drill_towel_arm', 'drill_hip_rotation', 'drill_half_swing']) {
      expect(getDrillVideoDetail(id)?.video_url).toMatch(/^https:\/\//)
    }
  })

  it('未知 drill 返回 null', () => {
    expect(getDrillVideoDetail('drill_unknown')).toBeNull()
  })

  it('resolveVideoCardDetail 支持直传 video_url', () => {
    const detail = resolveVideoCardDetail({
      title: '自定义',
      video_url: 'https://example.com/demo.mp4',
    })
    expect(detail?.video_url).toBe('https://example.com/demo.mp4')
  })
})
