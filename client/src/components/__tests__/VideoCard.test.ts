import VideoCard from '../VideoCard'
import { resolveVideoCardDetail } from '@/constants/drillVideoLibrary'
import type { VideoCardAttachment } from '@/types/chat'

describe('VideoCard', () => {
  it('导出组件', () => {
    expect(VideoCard).toBeDefined()
  })

  it('已知 drill_id 可解析示范视频', () => {
    const detail = resolveVideoCardDetail({ drill_id: 'drill_towel_arm' })
    expect(detail?.video_url).toContain('.mp4')
    expect(detail?.title).toContain('毛巾')
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
