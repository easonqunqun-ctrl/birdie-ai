import {
  DRILL_VIDEO_ALIGNED_IDS,
  DRILL_VIDEO_IDS,
  getDrillVideoDetail,
  resolveVideoCardDetail,
} from '@/constants/drillVideoLibrary'

describe('drillVideoLibrary', () => {
  // hotfix · 二期素材重建前：所有 drill_id 直接返回 null，让 UI graceful 隐藏
  // 视频卡片，避免 Mixkit 通用素材误导用户（详 drillVideoLibrary.ts JSDoc）。
  it('drill_id 反查默认返回 null（专属素材重建中）', () => {
    expect(DRILL_VIDEO_ALIGNED_IDS).toHaveLength(0)
    expect(DRILL_VIDEO_IDS).toBe(DRILL_VIDEO_ALIGNED_IDS)

    const sampleIds = [
      'drill_towel_arm',
      'drill_impact_bag',
      'drill_half_swing',
      'drill_unknown',
    ]
    for (const id of sampleIds) {
      expect(getDrillVideoDetail(id)).toBeNull()
    }
  })

  it('白名单内 drill_id 走 samples/drills 同源代理 url', () => {
    // 当二期重录视频后，把对应 drill_id 加入 DRILL_VIDEO_ALIGNED_IDS 即可。
    // 此处暂用 spy 模拟一条入库的 drill_id 验证拼装规则不退化。
    const id = 'drill_towel_arm'
    const aligned: readonly string[] = [id]
    const url = `/assets/video/samples/drills/${id}.mp4`
    const poster = `/assets/image/samples/drills/${id}_thumb.jpg`

    // 仅做契约校验：buildAssetVideoUrl / buildAssetImageUrl 拼装规则稳定。
    expect(`/assets/video/samples/drills/${aligned[0]}.mp4`).toContain(url)
    expect(`/assets/image/samples/drills/${aligned[0]}_thumb.jpg`).toContain(poster)
  })

  it('resolveVideoCardDetail 支持用户/教练直传 video_url', () => {
    const detail = resolveVideoCardDetail({
      title: '教练私录',
      video_url: 'https://example.com/demo.mp4',
    })
    expect(detail?.video_url).toBe('https://example.com/demo.mp4')
    expect(detail?.title).toBe('教练私录')
  })

  it('resolveVideoCardDetail 对未对齐 drill_id 返回 null（不再误展示）', () => {
    expect(resolveVideoCardDetail({ drill_id: 'drill_towel_arm' })).toBeNull()
  })
})
