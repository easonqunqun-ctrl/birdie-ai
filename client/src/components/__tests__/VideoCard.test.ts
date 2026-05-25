import VideoCard from '../VideoCard'
import { resolveVideoCardDetail } from '@/constants/drillVideoLibrary'
import type { VideoCardAttachment } from '@/types/chat'

describe('VideoCard', () => {
  it('导出组件', () => {
    expect(VideoCard).toBeDefined()
  })

  it('未对齐的 drill_id 不再返回 stock 素材（hotfix 防误导）', () => {
    expect(resolveVideoCardDetail({ drill_id: 'drill_towel_arm' })).toBeNull()
  })

  it('用户/教练直传 video_url 时仍可正常渲染（M8 教练上传场景）', () => {
    const detail = resolveVideoCardDetail({
      drill_id: 'drill_half_swing',
      title: '教练录制',
      video_url: 'https://example.com/coach.mp4',
    })
    expect(detail?.video_url).toBe('https://example.com/coach.mp4')
    expect(detail?.title).toBe('教练录制')
  })

  it('VideoCardAttachment 类型字段', () => {
    const att: VideoCardAttachment = {
      type: 'video_card',
      drill_id: 'drill_half_swing',
      title: '半挥杆节奏练习示范',
    }
    expect(att.drill_id).toBe('drill_half_swing')
  })
})
