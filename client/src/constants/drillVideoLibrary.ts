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
 *   - **PP-08 优先 3 条**见 `PP08_PRIORITY_DRILL_IDS`；片子到了且产品签字后
 *     **只把这几个 id** 写入 `DRILL_VIDEO_ALIGNED_IDS`，禁止把 Mixkit 旧片加回。
 *   - 上传：本地 `{drill_id}.mp4` → `bash scripts/drill-demo-videos/upload-aligned.sh <dir>`
 *     → MinIO `samples/drills/{drill_id}.mp4`（同源代理，前端拼装不用改）。
 *   - 用户直传 video_url（如 attachment 里带）的路径 **不受影响**，
 *     `resolveVideoCardDetail` 仍可正常解析；为 M8 / M12 自定义视频留余地。
 *
 * 重建计划：详见 [`docs/release-notes/drill-demo-video-revamp.md`](
 *   ../../../docs/release-notes/drill-demo-video-revamp.md)
 *   与 [`product-2week-close-2026-09-12.md`](
 *   ../../../docs/release-notes/product-2week-close-2026-09-12.md) §四。
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
 * **当前为空**：等 PP-08 成片 + 产品确认画面与步骤一致后再写入。
 */
export const DRILL_VIDEO_ALIGNED_IDS: readonly string[] = [] as const

/**
 * PP-08 两周窗口优先拍摄的 drill（最少 3 条出门）。
 * 仅作拍摄 / 上传脚本白名单，**不等于**已上架。
 */
export const PP08_PRIORITY_DRILL_IDS = [
  'drill_weight_shift',
  'drill_hip_rotation',
  'drill_towel_arm',
  'drill_alignment_stick',
  'drill_half_swing',
] as const

export const PP08_MUST_SHIP_DRILL_IDS = [
  'drill_weight_shift',
  'drill_hip_rotation',
  'drill_towel_arm',
] as const

export function isPp08PriorityDrill(drillId: string): boolean {
  return (PP08_PRIORITY_DRILL_IDS as readonly string[]).includes(drillId)
}

/** MinIO / 同源代理 object key（上传脚本与前端拼装共用约定） */
export function drillVideoObjectKey(drillId: string): string {
  return `samples/drills/${drillId}.mp4`
}

export function drillPosterObjectKey(drillId: string): string {
  return `samples/drills/${drillId}_thumb.jpg`
}

/**
 * @deprecated v1.1.1 时按全部 13 个 drill_id 拼 Mixkit 通用视频造成误导。
 * 历史代码若仍引用此常量请改用 `DRILL_VIDEO_ALIGNED_IDS`；
 * 该别名保留是为了避免外部消费方瞬间 TS 编译失败。
 */
export const DRILL_VIDEO_IDS = DRILL_VIDEO_ALIGNED_IDS

function drillVideoKey(drillId: string): string {
  return drillVideoObjectKey(drillId)
}

function drillPosterKey(drillId: string): string {
  return drillPosterObjectKey(drillId)
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
