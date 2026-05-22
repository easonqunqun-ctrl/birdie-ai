import {
  DRILL_VIDEO_IDS,
  getDrillVideoDetail,
  resolveVideoCardDetail,
} from '@/constants/drillVideoLibrary'

describe('drillVideoLibrary', () => {
  it('13 个 drill 均有独立同源代理视频', () => {
    expect(DRILL_VIDEO_IDS).toHaveLength(13)
    for (const id of DRILL_VIDEO_IDS) {
      const detail = getDrillVideoDetail(id)
      expect(detail?.video_url).toContain(`/assets/video/samples/drills/${id}.mp4`)
      expect(detail?.poster_url).toContain(`/assets/image/samples/drills/${id}_thumb.jpg`)
      expect(detail?.title).toContain('动作参考')
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
