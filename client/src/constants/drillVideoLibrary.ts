/**
 * 练习示范视频库（drill_id → 演示视频）
 *
 * 历史背景（v1.1.1）：曾用 Mixkit 通用高尔夫 stock 素材按 drill_id 直接拼装，
 * 但素材内容（如「爸爸教孩子打高尔夫」「老年女性打球」）与文字步骤
 * （如「毛巾夹臂练习」「臀贴墙练习」）**完全不对应**，反而误导用户。
 *
 * 当前状态（**hotfix · 二期素材重建前**）：
 *   - DRILL_VIDEO_ALIGNED_IDS 暂为空 → `getDrillVideoDetail` 对所有 drill_id
 *     都返回 null → 训练页 / AI 教练对话页 / 报告页**不再渲染错配视频卡片**，
 *     用户只看文字步骤与配图，避免被误导。
 *   - 链路保持完整：当 M8 教练上传自定义视频或 M11 课程体系上线后，
 *     重新把对应 drill_id 加回 DRILL_VIDEO_ALIGNED_IDS 即恢复展示。
 *   - 用户直传 video_url（如 attachment 里带）的路径 **不受影响**，
 *     `resolveVideoCardDetail` 仍可正常解析；为 M8 / M12 自定义视频留余地。
 *
 * 重建计划：详见 [`docs/release-notes/drill-demo-video-revamp.md`](
 *   ../../../docs/release-notes/drill-demo-video-revamp.md)
 * 素材 key 仍按 `samples/drills/{drill_id}.mp4` 约定（CVM MinIO 同源代理），
 * 二期重录视频上传同路径即可，无需改前端代码。
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

/**
 * **已校准对齐**的 drill 视频白名单。
 *
 * 加入此列表前，必须满足：
 *   1. 视频内容与 drillLibrary 中对应 drill 的「name + steps」一一呼应；
 *   2. 拍摄机位、教练资质、画质达白皮书 §7.2 / docs/21 §九 录制规范；
 *   3. 视频文件已上传至 MinIO `samples/drills/{drill_id}.mp4`
 *      且海报 `{drill_id}_thumb.jpg` 同步就位。
 *
 * **当前为空**：等待二期专属素材库（详见上方 JSDoc 与重建文档）。
 */
export const DRILL_VIDEO_ALIGNED_IDS: readonly string[] = [] as const

/**
 * @deprecated v1.1.1 时按全部 13 个 drill_id 拼 Mixkit 通用视频造成误导。
 * 历史代码若仍引用此常量请改用 `DRILL_VIDEO_ALIGNED_IDS`；
 * 该别名保留是为了避免外部消费方瞬间 TS 编译失败。
 */
export const DRILL_VIDEO_IDS = DRILL_VIDEO_ALIGNED_IDS

function drillVideoKey(drillId: string): string {
  return `samples/drills/${drillId}.mp4`
}

function drillPosterKey(drillId: string): string {
  return `samples/drills/${drillId}_thumb.jpg`
}

/** 示范视频卡片标题后缀（专属示范片，与文字步骤一一呼应） */
export const DRILL_VIDEO_TITLE_SUFFIX = ' · 教练示范'

function buildDrillVideoDetail(drillId: string): DrillVideoDetail {
  const drill = getDrillDetail(drillId)
  return {
    drill_id: drillId,
    title: `${drill.name}${DRILL_VIDEO_TITLE_SUFFIX}`,
    video_url: buildAssetVideoUrl(drillVideoKey(drillId)),
    poster_url: buildAssetImageUrl(drillPosterKey(drillId)),
  }
}

const DRILL_VIDEOS: DrillVideoDetail[] = DRILL_VIDEO_ALIGNED_IDS.map(buildDrillVideoDetail)

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
