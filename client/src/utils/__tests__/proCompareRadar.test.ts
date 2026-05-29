import {
  buildProPhaseCompareRows,
  buildProRadarAxes,
  buildUserRadarAxes,
  deriveProPhaseScores,
  proScoresAreReferenceOnly,
} from '@/utils/proCompareRadar'
import type { AnalysisReportResponse } from '@/types/analysis'
import type { ProSwingClipRead } from '@/services/prosService'

const sampleReport: AnalysisReportResponse = {
  id: 'ana_test',
  status: 'completed',
  camera_angle: 'face_on',
  club_type: 'iron_7',
  video_url: 'https://x/v.mp4',
  issues: [],
  recommendations: [],
  created_at: '2026-01-01T00:00:00Z',
  phase_scores: {
    setup: { score: 80, label: '准备', is_weakest: false },
    takeaway: { score: 78, label: '上杆', is_weakest: false },
    top: { score: 82, label: '顶点', is_weakest: false },
    downswing: { score: 75, label: '下杆', is_weakest: true },
    impact: { score: 79, label: '击球', is_weakest: false },
    follow_through: { score: 81, label: '收杆', is_weakest: false },
  },
}

const sampleClip: ProSwingClipRead = {
  id: 'psc_x',
  pro_player_id: 'pp_x',
  club_type: 'iron_7',
  camera_angle: 'face_on',
  video_url: 'https://example.com/x.mp4',
  thumbnail_url: null,
  duration_ms: 4000,
  fps: 60,
  overall_score: 92,
  engine_version: 'v1',
  features_snapshot: { shoulder_turn_deg: 92 },
  license_status: 'public_clip',
  source_credit: 'demo',
  source_url: 'https://example.com/meta',
  captured_year: 2026,
  is_published: true,
}

describe('proCompareRadar', () => {
  test('buildUserRadarAxes preserves phase order', () => {
    const axes = buildUserRadarAxes(sampleReport)
    expect(axes).toHaveLength(6)
    expect(axes[0].key).toBe('setup')
    expect(axes[3].is_weakest).toBe(true)
  })

  test('deriveProPhaseScores falls back to overall_score', () => {
    const scores = deriveProPhaseScores(sampleClip)
    expect(scores.setup).toBe(92)
    expect(proScoresAreReferenceOnly(sampleClip)).toBe(true)
  })

  test('deriveProPhaseScores uses phase keys from snapshot when present', () => {
    const clip: ProSwingClipRead = {
      ...sampleClip,
      features_snapshot: { setup: 88, impact: 90 },
    }
    expect(deriveProPhaseScores(clip).setup).toBe(88)
    expect(deriveProPhaseScores(clip).impact).toBe(90)
    expect(proScoresAreReferenceOnly(clip)).toBe(false)
  })

  test('buildProRadarAxes aligns with user axes length', () => {
    const userAxes = buildUserRadarAxes(sampleReport)
    const proAxes = buildProRadarAxes(sampleClip, userAxes)
    expect(proAxes).toHaveLength(userAxes.length)
    expect(proAxes.every((ax) => ax.score === 92)).toBe(true)
  })

  test('buildProPhaseCompareRows computes delta', () => {
    const rows = buildProPhaseCompareRows(sampleReport, sampleClip)
    const setup = rows.find((r) => r.key === 'setup')
    expect(setup?.userScore).toBe(80)
    expect(setup?.proScore).toBe(92)
    expect(setup?.delta).toBe(-12)
  })
})
