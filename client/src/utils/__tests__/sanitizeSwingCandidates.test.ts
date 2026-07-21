import {
  MIN_SWING_CANDIDATE_DURATION_SEC,
  sanitizeSwingCandidates,
  swingCandidateDurationSec,
} from '../sanitizeSwingCandidates'
import type { SwingCandidateItem } from '@/types/analysis'

function cand(
  partial: Partial<SwingCandidateItem> &
    Pick<SwingCandidateItem, 'start_frame' | 'end_frame' | 'start_time_sec' | 'end_time_sec'>,
): SwingCandidateItem {
  return {
    is_practice: false,
    confidence: 0.9,
    ...partial,
  }
}

describe('sanitizeSwingCandidates', () => {
  test('drops near-zero duration pseudo practice', () => {
    const input = [
      cand({
        start_frame: 0,
        end_frame: 3,
        start_time_sec: 0,
        end_time_sec: 0.1,
        is_practice: true,
      }),
      cand({
        start_frame: 90,
        end_frame: 180,
        start_time_sec: 3,
        end_time_sec: 6,
        is_practice: false,
      }),
    ]
    const out = sanitizeSwingCandidates(input, 1)
    expect(out.swing_candidates).toHaveLength(1)
    expect(out.swing_candidates[0].is_practice).toBe(false)
    expect(out.default_selected_index).toBe(0)
  })

  test('keeps all when every segment is long enough', () => {
    const input = [
      cand({
        start_frame: 0,
        end_frame: 60,
        start_time_sec: 0,
        end_time_sec: 2,
        is_practice: true,
      }),
      cand({
        start_frame: 90,
        end_frame: 180,
        start_time_sec: 3,
        end_time_sec: 6,
        is_practice: false,
      }),
    ]
    const out = sanitizeSwingCandidates(input, 1)
    expect(out.swing_candidates).toHaveLength(2)
    expect(out.default_selected_index).toBe(1)
  })

  test('duration helper', () => {
    expect(
      swingCandidateDurationSec(
        cand({
          start_frame: 0,
          end_frame: 30,
          start_time_sec: 1,
          end_time_sec: 1.6,
        }),
      ),
    ).toBeCloseTo(0.6)
  })
})
