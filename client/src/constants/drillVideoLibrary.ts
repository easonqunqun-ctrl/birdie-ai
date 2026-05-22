/**
 * 练习示范视频库（drill_id → 演示视频）
 *
 * 生产环境仅 trust ``drill_id`` 本地库 lookup；``video_url`` 直传仅供测试/后续 COS 白名单素材。
 * 视频 URL 与 backend `sample_fixture.SAMPLE_VIDEO_URL` 同源占位，后续可换 COS 真素材。
 */

export interface DrillVideoDetail {
  drill_id: string
  title: string
  video_url: string
  poster_url?: string
  duration_seconds?: number
}

const SAMPLE_VIDEO_URL =
  'https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4'
const SAMPLE_POSTER_URL =
  'https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo_thumb.jpg'

const DRILL_VIDEOS: DrillVideoDetail[] = [
  {
    drill_id: 'drill_towel_arm',
    title: '毛巾夹臂练习示范',
    video_url: SAMPLE_VIDEO_URL,
    poster_url: SAMPLE_POSTER_URL,
    duration_seconds: 45,
  },
  {
    drill_id: 'drill_hip_rotation',
    title: '髋部旋转练习示范',
    video_url: SAMPLE_VIDEO_URL,
    poster_url: SAMPLE_POSTER_URL,
    duration_seconds: 52,
  },
  {
    drill_id: 'drill_half_swing',
    title: '半挥杆节奏练习示范',
    video_url: SAMPLE_VIDEO_URL,
    poster_url: SAMPLE_POSTER_URL,
    duration_seconds: 38,
  },
]

const VIDEO_MAP: Record<string, DrillVideoDetail> = DRILL_VIDEOS.reduce(
  (acc, item) => {
    acc[item.drill_id] = item
    return acc
  },
  {} as Record<string, DrillVideoDetail>,
)

export function getDrillVideoDetail(drillId: string): DrillVideoDetail | null {
  return VIDEO_MAP[drillId] ?? null
}

export function resolveVideoCardDetail(input: {
  drill_id?: string
  title?: string
  video_url?: string
  poster_url?: string
}): DrillVideoDetail | null {
  if (input.video_url) {
    return {
      drill_id: input.drill_id || 'video_custom',
      title: input.title || '练习示范',
      video_url: input.video_url,
      poster_url: input.poster_url,
    }
  }
  if (input.drill_id) {
    const base = getDrillVideoDetail(input.drill_id)
    if (!base) return null
    return {
      ...base,
      title: input.title || base.title,
    }
  }
  return null
}
