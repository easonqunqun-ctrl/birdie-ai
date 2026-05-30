/**
 * 挥杆分析端到端类型声明
 *
 * 与 `backend/app/schemas/analysis.py` 严格对齐。所有新字段出现在后端时，
 * 这里必须同步更新；前后端契约以本文件为准。
 *
 * 注：已有的通用分析结构（SwingAnalysis / AnalysisIssue / AnalysisRecommendation 等）
 * 仍保留在 `./api.ts` 中供旧代码引用；本文件聚焦 T3 新增的上传 / 任务创建 / 轮询
 * 所需的入参与出参 DTO。
 */

import type { CameraAngle, ClubType, PageData } from './api'

/* ==================== 上传凭证 ==================== */
export interface UploadTokenRequest {
  file_name: string
  file_size: number
  file_type: string // 'video/mp4' | 'video/quicktime'
  duration: number // 秒
}

export interface UploadTokenResponse {
  upload_id: string
  /** MinIO / COS bucket URL，供前端 POST multipart 到此 */
  upload_url: string
  /** 服务端约定的对象 key，必须回填到 form fields 里的 `key` 字段 */
  key: string
  /** 后端已在 fields 里放好 `key / Content-Type / policy / signature / ...`，前端原样转发 */
  fields: Record<string, string>
  expires_at: string
}

/* ==================== 创建任务 ==================== */
export type AnalysisMode = 'full_swing' | 'putting' | 'chipping'

export interface CreateAnalysisRequest {
  upload_id: string
  camera_angle: CameraAngle
  club_type: ClubType
  /** M10-01：分析模式；默认 full_swing */
  mode?: AnalysisMode
  /** M10-03：全挥杆目标码数（可选），供 yardage book 历史反推 */
  target_yardage?: number
  /** M7-13：多挥视频段索引（0-based）；仅 full_swing */
  selected_swing_index?: number
}

/** M7-13 · 单段挥杆候选 */
export interface SwingCandidateItem {
  start_frame: number
  end_frame: number
  is_practice: boolean
  confidence: number
  start_time_sec: number
  end_time_sec: number
  /** detect-swings 按段抽帧预览（backend 同源代理 URL） */
  preview_frame_url?: string | null
}

export interface DetectSwingsResponse {
  upload_id: string
  swing_candidates: SwingCandidateItem[]
  default_selected_index: number
}

export interface CreateAnalysisResponse {
  analysis_id: string
  status: 'pending' | 'processing'
  /** 队列里排在前面的任务数（仅参考） */
  queue_position: number
  /** 按 25s 基线估算的剩余秒数；精度不高，等待页本地倒计时即可 */
  estimated_seconds: number
  created_at: string
}

/* ==================== 状态查询 ==================== */
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type AnalysisStage =
  | 'preprocessing'
  | 'pose_estimating'
  | 'phase_segmenting'
  | 'scoring'
  | 'diagnosing'
  | 'generating'

export interface AnalysisErrorInfo {
  code: number
  message: string
  /** 配额是否已退回（仅 failed 时出现） */
  quota_refunded?: boolean
}

export interface AnalysisStatusResponse {
  analysis_id: string
  status: AnalysisStatus
  stage: AnalysisStage | null
  stage_progress: number // 0-100
  /** 剩余秒数估算；可能为 0 或 null */
  estimated_remaining_seconds: number | null
  error: AnalysisErrorInfo | null
}

/* ==================== 报告查询（T5 用） ==================== */
export interface PhaseScore {
  score: number
  label: string
  is_weakest: boolean
}

export interface PhaseWindow {
  start: number
  end: number
}

/** P2-M7-06：每诊断置信度档位（与 backend Literal 1:1） */
export type IssueConfidenceTier = 'confirmed' | 'leaning' | 'hidden'

export interface AnalysisIssueDetail {
  type: string
  name: string
  severity: 'high' | 'medium' | 'low'
  description: string
  key_frame_url?: string | null
  key_frame_timestamp?: number | null
  /**
   * P2-M7-06 + W10：每诊断置信度 0-1（V1 引擎为 null）+ 档位。
   * 客户端按 confidence_tier 区分展示：
   * - confirmed: 正常展示
   * - leaning:   描述前缀加"可能存在……"语气
   * - hidden:    默认折叠到「AI 不太确定」可展开区，避免低质量诊断打扰用户
   */
  confidence?: number | null
  confidence_tier?: IssueConfidenceTier | null
}

/** P2-W10：W8 引擎诊断结构化条目（codec/HDR/慢动作/fps/audio/fallback） */
export interface EngineWarning {
  code: string
  level: 'info' | 'warn' | 'error'
  detail?: string | null
  ts?: number | null
}

export interface AnalysisRecommendationDetail {
  drill_id: string
  target_issue: string | null
  /** 排序权重；sort_order 越小越靠前 */
  sort_order?: number
}

/** 评分分级（和 backend/app/schemas/analysis.py::score_level 保持同步） */
export type AnalysisScoreLevel =
  | 'excellent'
  | 'great'
  | 'good'
  | 'fair'
  | 'needs_improvement'

export interface AnalysisReportResponse {
  id: string
  /** 后端返回 user_id；一般前端不展示，只用来埋点或校对 */
  user_id?: string
  status: AnalysisStatus
  camera_angle: CameraAngle
  club_type: ClubType
  /** M10-01：分析模式；老报告缺省 full_swing */
  analysis_mode?: AnalysisMode | null
  /** M10-01：推杆专属 4 维度；仅 analysis_mode=putting */
  putting_features?: Record<string, PhaseScore> | null
  /** M10-02：切杆专属 3 维度；仅 analysis_mode=chipping */
  chipping_features?: Record<string, PhaseScore> | null
  video_url: string
  /** 视频时长（秒）；backend 会返回 decimal 转 float */
  video_duration?: number | null
  skeleton_video_url?: string | null
  skeleton_data_url?: string | null
  thumbnail_url?: string | null
  overall_score?: number | null
  score_level?: AnalysisScoreLevel | null
  score_change?: number | null
  phase_scores?: Record<string, PhaseScore> | null
  phase_timestamps?: Record<string, PhaseWindow> | null
  issues: AnalysisIssueDetail[]
  recommendations: AnalysisRecommendationDetail[]
  /**
   * 非阻断质量提示（引擎 machine codes），如 low_light / camera_shake；
   * 空数组或未返回表示无附加提示。
   */
  quality_warnings?: string[] | null
  /**
   * P2-M7-06：整体 AI 可信度 0-1。
   * V1 引擎报告兜底 1.0；客户端 <0.5 触发 TrustBadge"建议重拍" CTA。
   * 字段一定有值（backend schema NOT NULL DEFAULT 1.0）。
   */
  analysis_confidence?: number | null
  /** P2-M7-06：每特征 confidence dict (feature_name → 0-1)；V1 引擎为 {} */
  feature_confidences?: Record<string, number> | null
  /**
   * P2-W10：W8 引擎诊断结构化条目，仅在报告页"调试浮层"展示，不在主报告区显眼。
   * V1 引擎或老报告为 [] / null。
   */
  engine_warnings?: EngineWarning[] | null
  /** 引擎版本：V1 / V2 灰度区分（W5+ 由 ai_engine 返回；老报告兜底 v1） */
  engine_version?: 'v1' | 'v2' | null
  /** 分享卡片（W7 再生成，MVP 期为 null） */
  share_card_url?: string | null
  error?: AnalysisErrorInfo | null
  created_at: string
  analyzed_at?: string | null
}

/* ==================== 列表 ==================== */
export interface AnalysisListItem {
  id: string
  status: AnalysisStatus
  club_type: ClubType
  camera_angle: CameraAngle
  thumbnail_url?: string | null
  overall_score?: number | null
  score_level?: AnalysisScoreLevel | null
  /** 与上一次同类型分析的分数差；可能为负 */
  score_change?: number | null
  analyzed_at?: string | null
  created_at: string
  // P2-W11：让历史卡片能贴 V2 可信度小标签（高/中/低）+ V2 角标
  // V1 / 老报告 engine_version 缺省 "v1"，analysis_confidence null 时前端不渲染小标签
  engine_version?: 'v1' | 'v2' | null
  analysis_confidence?: number | null
}

/** 免费用户历史报告被截断时的元信息（与 backend AnalysisListPaywall 对齐）。 */
export interface AnalysisListPaywall {
  reason: 'free_user_history_limit' | string
  /** 免费用户最多可见的份数（当前 3） */
  capped_to: number
  /** 用户实际拥有的真实总数（含被截断的） */
  total_count: number
}

/**
 * `GET /v1/analyses` 响应：在 PageData 上叠加 `paywall`。
 *
 * `paywall == null` 表示无截断（会员或免费用户报告数 ≤ capped_to）。
 */
export interface AnalysisListResponse extends PageData<AnalysisListItem> {
  paywall?: AnalysisListPaywall | null
}

/* ==================== 前端校验常量 ==================== */
export const VIDEO_CONSTRAINTS = {
  MIN_DURATION_SECONDS: 2,
  MAX_DURATION_SECONDS: 30,
  MAX_SIZE_BYTES: 100 * 1024 * 1024,
  ACCEPTED_EXTENSIONS: ['mp4', 'mov'] as const,
} as const

/* ==================== UI 标签映射 ==================== */
export const CAMERA_ANGLE_LABEL: Record<CameraAngle, string> = {
  face_on: '正面（Face-On）',
  down_the_line: '侧面（Down-the-Line）',
}

export const CAMERA_ANGLE_DESC: Record<CameraAngle, string> = {
  face_on: '站在球员正对面拍摄，看挥杆平面与重心',
  down_the_line: '沿击球方向延长线拍摄，看挥杆轨迹',
}

export const CLUB_TYPE_LABEL: Record<ClubType, string> = {
  driver: '1 号木（Driver）',
  fairway_wood: '球道木',
  iron_3: '3 号铁',
  iron_4: '4 号铁',
  iron_5: '5 号铁',
  iron_6: '6 号铁',
  iron_7: '7 号铁',
  iron_8: '8 号铁',
  iron_9: '9 号铁',
  wedge: '挖起杆（Wedge）',
  putter: '推杆（Putter）',
  unknown: '其他 / 不确定',
}

/** UI 上按常用度分组（默认选中 7 号铁） */
export const CLUB_TYPE_GROUPS: { title: string; items: ClubType[] }[] = [
  { title: '木杆', items: ['driver', 'fairway_wood'] },
  { title: '铁杆', items: ['iron_3', 'iron_5', 'iron_7', 'iron_9'] },
  { title: '其他', items: ['wedge', 'putter', 'unknown'] },
]
