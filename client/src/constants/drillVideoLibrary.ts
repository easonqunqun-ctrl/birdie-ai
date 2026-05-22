/**
 * 练习示范视频库（drill_id → 演示视频）
 *
 * 素材 key 与 CVM MinIO `samples/drills/` 一致，经 `{API}/v1/assets/…` 同源代理播放。
 * 源视频清单与 Mixkit 授权见 `scripts/drill-demo-videos/manifest.json`。
 */

import { getDrillDetail } from '@/constants/drillLibrary'
import { buildAssetImageUrl, buildAssetVideoUrl } from '@/utils/assetUrls'

export interface DrillVideoDetail {
  drill_id: string
  title: string
  video_url: string
  poster_url?: string
  duration_seconds?: number
}

/** 与 drillLibrary / mock_pipeline 同步的 13 个 drill，均有独立示范片 */
export const DRILL_VIDEO_IDS = [
  'drill_towel_arm',
  'drill_impact_bag',
  'drill_half_swing',
  'drill_inside_path',
  'drill_wall_butt',
  'drill_hip_rotation',
  'drill_mirror_spine',
  'drill_weight_shift',
  'drill_backswing_stop',
  'drill_shoulder_turn',
  'drill_plane_board',
  'drill_alignment_stick',
  'drill_grip_checkpoint',
] as const

function drillVideoKey(drillId: string): string {
  return `samples/drills/${drillId}.mp4`
}

function drillPosterKey(drillId: string): string {
  return `samples/drills/${drillId}_thumb.jpg`
}

/** 示范视频卡片标题后缀（素材为通用参考片段，非专属教程） */
export const DRILL_VIDEO_TITLE_SUFFIX = ' · 动作参考'

function buildDrillVideoDetail(drillId: string): DrillVideoDetail {
  const drill = getDrillDetail(drillId)
  return {
    drill_id: drillId,
    title: `${drill.name}${DRILL_VIDEO_TITLE_SUFFIX}`,
    video_url: buildAssetVideoUrl(drillVideoKey(drillId)),
    poster_url: buildAssetImageUrl(drillPosterKey(drillId)),
  }
}

const DRILL_VIDEOS: DrillVideoDetail[] = DRILL_VIDEO_IDS.map(buildDrillVideoDetail)

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
