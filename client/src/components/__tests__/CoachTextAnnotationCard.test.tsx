import { render, screen, fireEvent } from '@testing-library/react'
import CoachTextAnnotationCard from '@/components/CoachTextAnnotationCard'
import type { CoachAnnotationClipRef } from '@/services/coachAnnotationService'

const baseAnn: CoachAnnotationClipRef = {
  id: 'can_1',
  analysis_id: 'ana_1',
  annotation_type: 'text',
  pro_clip_id: null,
  text_content: '注意送杆完整',
  is_visible: true,
  created_at: '2026-01-01T00:00:00Z',
  clip: null,
  player: null,
  clip_unavailable: false,
}

describe('CoachTextAnnotationCard', () => {
  test('renders coach comment text', () => {
    render(<CoachTextAnnotationCard annotation={baseAnn} />)
    expect(screen.getByText('教练点评')).toBeTruthy()
    expect(screen.getByText('注意送杆完整')).toBeTruthy()
  })

  test('shows delete when onDelete provided', () => {
    const onDelete = jest.fn()
    render(<CoachTextAnnotationCard annotation={baseAnn} onDelete={onDelete} />)
    fireEvent.click(screen.getByText('删除'))
    expect(onDelete).toHaveBeenCalledWith('can_1')
  })
})
