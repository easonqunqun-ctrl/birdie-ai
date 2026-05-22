import {
  getDrillVideoDetail,
  resolveVideoCardDetail,
} from '@/constants/drillVideoLibrary'

describe('drillVideoLibrary', () => {
  it('三大 heuristic drill 均有同源代理视频', () => {
    for (const id of ['drill_towel_arm', 'drill_hip_rotation', 'drill_half_swing']) {
      const detail = getDrillVideoDetail(id)
      expect(detail?.video_url).toContain('/assets/video/samples/swing_demo.mp4')
      expect(detail?.poster_url).toContain('/assets/image/samples/swing_demo_thumb.jpg')
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
