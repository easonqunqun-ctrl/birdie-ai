import {
  shouldContinueSkeletonPoll,
  shouldPollSkeletonPending,
  SKELETON_POLL_MAX_TRIES,
} from '@/utils/skeletonPendingPoll'

describe('skeletonPendingPoll', () => {
  test('pending 且无骨骼 URL → 应轮询', () => {
    expect(
      shouldPollSkeletonPending({
        skeleton_video_url: null,
        engine_warnings: [{ code: 'skeleton_pending' }],
      }),
    ).toBe(true)
  })

  test('已有骨骼 URL → 不轮询', () => {
    expect(
      shouldPollSkeletonPending({
        skeleton_video_url: 'https://x/skeleton.mp4',
        engine_warnings: [{ code: 'skeleton_pending' }],
      }),
    ).toBe(false)
  })

  test('无 pending 警告 → 不轮询', () => {
    expect(
      shouldPollSkeletonPending({
        skeleton_video_url: null,
        engine_warnings: [{ code: 'fps_downsampled' }],
      }),
    ).toBe(false)
  })

  test('达到 maxTries 后停止', () => {
    const report = {
      skeleton_video_url: null as string | null,
      engine_warnings: [{ code: 'skeleton_pending' }],
    }
    expect(shouldContinueSkeletonPoll(report, SKELETON_POLL_MAX_TRIES - 1)).toBe(true)
    expect(shouldContinueSkeletonPoll(report, SKELETON_POLL_MAX_TRIES)).toBe(false)
  })
})
