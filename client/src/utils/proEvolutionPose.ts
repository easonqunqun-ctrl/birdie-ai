/**
 * P2-M12-08 · 从报告问题 + 职业镜头 features_snapshot 解析演化示意场景。
 */

import type { AnalysisReportResponse } from '@/types/analysis'
import type { ProSwingClipRead } from '@/services/prosService'
import { parsePoseKeypoints, type PoseKeypoints } from '@/utils/posInterpolate'

export type EvolutionScenarioKey =
  | 'early_extension'
  | 'chicken_wing'
  | 'reverse_spine'

export interface EvolutionScene {
  key: EvolutionScenarioKey
  label: string
  userPose: PoseKeypoints
  proPose: PoseKeypoints
}

const ISSUE_TO_SCENARIO: Record<string, EvolutionScenarioKey> = {
  early_extension: 'early_extension',
  chicken_wing: 'chicken_wing',
  trail_elbow_break: 'chicken_wing',
  reverse_spine: 'reverse_spine',
  loss_of_posture: 'reverse_spine',
}

const SCENARIO_ORDER: EvolutionScenarioKey[] = [
  'early_extension',
  'chicken_wing',
  'reverse_spine',
]

const SCENARIO_LABEL: Record<EvolutionScenarioKey, string> = {
  early_extension: '早伸修复示意',
  chicken_wing: '鸡翼肘改善示意',
  reverse_spine: '脊柱回正示意',
}

function readEvolutionPoses(
  clip: ProSwingClipRead,
): Partial<Record<EvolutionScenarioKey, { label?: string; user: unknown; pro: unknown }>> {
  const snap = clip.features_snapshot ?? {}
  const raw = snap.evolution_poses
  if (!raw || typeof raw !== 'object') return {}
  return raw as Partial<
    Record<EvolutionScenarioKey, { label?: string; user: unknown; pro: unknown }>
  >
}

function pickScenarioKey(report: AnalysisReportResponse): EvolutionScenarioKey | null {
  for (const issue of report.issues) {
    const mapped = ISSUE_TO_SCENARIO[issue.name]
    if (mapped) return mapped
  }
  return null
}

function buildScene(
  key: EvolutionScenarioKey,
  bundle: { label?: string; user: unknown; pro: unknown },
): EvolutionScene | null {
  const userPose = parsePoseKeypoints(bundle.user)
  const proPose = parsePoseKeypoints(bundle.pro)
  if (!userPose || !proPose) return null
  return {
    key,
    label: bundle.label?.trim() || SCENARIO_LABEL[key],
    userPose,
    proPose,
  }
}

/** 解析演化场景；无可用 pose 时返回 null（调用方降级雷达渐变）。 */
export function resolveEvolutionScene(
  report: AnalysisReportResponse,
  clip: ProSwingClipRead,
): EvolutionScene | null {
  const poses = readEvolutionPoses(clip)
  const preferred = pickScenarioKey(report)
  if (preferred && poses[preferred]) {
    const scene = buildScene(preferred, poses[preferred]!)
    if (scene) return scene
  }
  for (const key of SCENARIO_ORDER) {
    const bundle = poses[key]
    if (!bundle) continue
    const scene = buildScene(key, bundle)
    if (scene) return scene
  }
  return null
}
