import { resolveEvolutionScene } from '@/utils/proEvolutionPose'
import type { AnalysisReportResponse } from '@/types/analysis'
import type { ProSwingClipRead } from '@/services/prosService'

const basePose = [
  { x: 0.5, y: 0.15 },
  { x: 0.5, y: 0.22 },
  { x: 0.42, y: 0.25 },
]

const clipWithPoses: ProSwingClipRead = {
  id: 'psc_1',
  pro_player_id: 'pp_1',
  club_type: 'iron_7',
  camera_angle: 'face_on',
  video_url: 'https://x/v.mp4',
  thumbnail_url: null,
  duration_ms: 1000,
  fps: 30,
  overall_score: 90,
  engine_version: 'v1',
  features_snapshot: {
    evolution_poses: {
      early_extension: {
        label: '早伸',
        user: basePose,
        pro: [
          { x: 0.5, y: 0.15 },
          { x: 0.5, y: 0.22 },
          { x: 0.44, y: 0.25 },
        ],
      },
      chicken_wing: {
        user: basePose,
        pro: basePose,
      },
    },
  },
  license_status: 'public_clip',
  source_credit: 'demo',
  source_url: 'https://x',
  captured_year: 2026,
  is_published: true,
}

function reportWithIssue(type: string, name?: string): AnalysisReportResponse {
  return {
    id: 'ana_1',
    status: 'completed',
    club_type: 'iron_7',
    camera_angle: 'face_on',
    overall_score: 70,
    video_url: 'https://x/v.mp4',
    recommendations: [],
    created_at: '2026-05-29T00:00:00Z',
    issues: [
      {
        type,
        name: name ?? type,
        severity: 'medium',
        description: 'test',
        confidence_tier: 'confirmed',
      },
    ],
  } as unknown as AnalysisReportResponse
}

describe('resolveEvolutionScene', () => {
  test('maps issue.type to matching scenario', () => {
    const scene = resolveEvolutionScene(
      reportWithIssue('early_extension'),
      clipWithPoses,
    )
    expect(scene?.key).toBe('early_extension')
    expect(scene?.label).toBe('早伸')
    expect(scene?.userPose[2].x).toBe(0.42)
    expect(scene?.proPose[2].x).toBe(0.44)
  })

  test('maps trail_elbow_break alias to chicken_wing', () => {
    const scene = resolveEvolutionScene(
      reportWithIssue('trail_elbow_break', '鸡翼肘'),
      clipWithPoses,
    )
    expect(scene?.key).toBe('chicken_wing')
  })

  test('all three demo scenarios parse from seed clip', () => {
    const fullClip: ProSwingClipRead = {
      ...clipWithPoses,
      features_snapshot: {
        evolution_poses: {
          early_extension: {
            user: basePose,
            pro: basePose,
          },
          chicken_wing: {
            user: basePose,
            pro: basePose,
          },
          reverse_spine: {
            user: basePose,
            pro: basePose,
          },
        },
      },
    }
    expect(resolveEvolutionScene(reportWithIssue('early_extension'), fullClip)?.key).toBe(
      'early_extension',
    )
    expect(resolveEvolutionScene(reportWithIssue('chicken_wing'), fullClip)?.key).toBe(
      'chicken_wing',
    )
    expect(resolveEvolutionScene(reportWithIssue('reverse_spine'), fullClip)?.key).toBe(
      'reverse_spine',
    )
  })

  test('falls back to first available scenario', () => {
    const scene = resolveEvolutionScene(reportWithIssue('unknown_issue'), clipWithPoses)
    expect(scene?.key).toBe('early_extension')
  })

  test('returns null when clip has no evolution_poses', () => {
    const clip = { ...clipWithPoses, features_snapshot: {} }
    expect(resolveEvolutionScene(reportWithIssue('early_extension'), clip)).toBeNull()
  })
})
