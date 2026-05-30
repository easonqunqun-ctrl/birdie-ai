import { render, screen, fireEvent } from '@testing-library/react'
import SkeletonAnimation from '@/components/SkeletonAnimation'
import type { PoseKeypoints } from '@/utils/posInterpolate'

jest.mock('@tarojs/components', () => ({
  View: ({ children, className, onClick }: React.PropsWithChildren<{ className?: string; onClick?: () => void }>) => (
    <div className={className} onClick={onClick}>
      {children}
    </div>
  ),
  Text: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => (
    <span className={className}>{children}</span>
  ),
  Canvas: ({ className }: { className?: string }) => <canvas className={className} />,
}))

jest.mock('@tarojs/taro', () => ({
  useReady: () => {},
  createSelectorQuery: () => ({
    select: () => ({
      fields: () => ({
        exec: (fn: (res: unknown[]) => void) => fn([]),
      }),
    }),
  }),
  getWindowInfo: () => ({ pixelRatio: 2 }),
  getSystemInfoSync: () => ({ pixelRatio: 2 }),
}))

const start: PoseKeypoints = [
  { x: 0.4, y: 0.2 },
  { x: 0.5, y: 0.3 },
]
const end: PoseKeypoints = [
  { x: 0.6, y: 0.2 },
  { x: 0.5, y: 0.3 },
]

describe('SkeletonAnimation', () => {
  test('renders caption and disclaimer', () => {
    render(<SkeletonAnimation start={start} end={end} caption='早伸修复示意' />)
    expect(screen.getByText('早伸修复示意')).toBeTruthy()
    expect(screen.getByText(/示意动画/)).toBeTruthy()
  })

  test('state tabs switch pose label', () => {
    render(<SkeletonAnimation start={start} end={end} />)
    fireEvent.click(screen.getByText('职业目标'))
    expect(screen.getByText('职业目标')).toBeTruthy()
  })

  test('play button toggles animating text', () => {
    render(<SkeletonAnimation start={start} end={end} />)
    fireEvent.click(screen.getByText('播放演化'))
    expect(screen.getByText('播放中…')).toBeTruthy()
  })
})
