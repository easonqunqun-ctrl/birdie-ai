import { render, screen, fireEvent } from '@testing-library/react'
import ProClipReferenceCard from '@/components/ProClipReferenceCard'
import type { CoachAnnotationClipRef } from '@/services/coachAnnotationService'

jest.mock('@tarojs/taro', () => ({
  navigateTo: jest.fn(),
}))

const baseAnn: CoachAnnotationClipRef = {
  id: 'can_2',
  analysis_id: 'ana_1',
  annotation_type: 'video_ref',
  pro_clip_id: 'psc_1',
  text_content: '参考节奏',
  is_visible: true,
  created_at: '2026-01-01T00:00:00Z',
  clip_unavailable: false,
  clip: {
    id: 'psc_1',
    pro_player_id: 'pro_1',
    club_type: 'iron_7',
    camera_angle: 'face_on',
    overall_score: 88,
    video_url: 'https://example.com/v.mp4',
    thumbnail_url: 'https://example.com/t.jpg',
    duration_ms: 8000,
    fps: 30,
    engine_version: 'v1',
    features_snapshot: {},
    license_status: 'public_clip',
    source_credit: 'demo',
    source_url: 'https://example.com',
    captured_year: 2024,
    is_published: true,
  },
  player: {
    id: 'pro_1',
    name: '示例球手',
    name_en: null,
    nationality: 'USA',
    handedness: 'right',
    height_cm: null,
    avatar_url: null,
    short_bio: null,
    license_status: 'public_clip',
    is_active: true,
    sort_order: 0,
  },
}

describe('ProClipReferenceCard', () => {
  test('renders player and compare actions', () => {
    render(<ProClipReferenceCard annotation={baseAnn} analysisId='ana_1' />)
    expect(screen.getByText('教练推荐参考')).toBeTruthy()
    expect(screen.getByText('示例球手')).toBeTruthy()
    expect(screen.getByText('看对比')).toBeTruthy()
  })

  test('shows unavailable fallback', () => {
    render(
      <ProClipReferenceCard
        annotation={{ ...baseAnn, clip_unavailable: true, clip: null, player: null }}
        analysisId='ana_1'
      />,
    )
    expect(screen.getByText('参考的职业镜头已下架')).toBeTruthy()
  })

  test('delete in coach mode', () => {
    const onDelete = jest.fn()
    render(
      <ProClipReferenceCard
        annotation={baseAnn}
        analysisId='ana_1'
        onDelete={onDelete}
      />,
    )
    fireEvent.click(screen.getByText('删除'))
    expect(onDelete).toHaveBeenCalledWith('can_2')
  })
})
