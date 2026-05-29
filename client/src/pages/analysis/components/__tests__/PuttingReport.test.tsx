import { render, screen } from '@testing-library/react'
import PuttingReport from '@/pages/analysis/components/PuttingReport'

jest.mock('@tarojs/components', () => ({
  View: ({ children, className, onClick }: any) => (
    <div className={className} onClick={onClick}>
      {children}
    </div>
  ),
  Text: ({ children, className }: any) => <span className={className}>{children}</span>,
}))

jest.mock('@/components/RadarChart', () => ({
  __esModule: true,
  default: ({ axes }: { axes: Array<{ label: string }> }) => (
    <div data-testid='radar'>{axes.map((a) => a.label).join(',')}</div>
  ),
}))

describe('PuttingReport', () => {
  test('renders four putting phases and four feature dimensions', () => {
    render(
      <PuttingReport
        phaseScores={{
          setup: { score: 82, label: '瞄准准备', is_weakest: false },
          backstroke: { score: 80, label: '回摆', is_weakest: false },
          impact: { score: 70, label: '击球', is_weakest: true },
          follow: { score: 85, label: '送杆', is_weakest: false },
        }}
        puttingFeatures={{
          pendulum_stability: { score: 84, label: '钟摆稳定度', is_weakest: false },
          head_stability: { score: 70, label: '头部稳定', is_weakest: true },
          face_alignment: { score: 78, label: '推杆面方正', is_weakest: false },
          tempo_ratio: { score: 86, label: '节奏比', is_weakest: false },
        }}
      />,
    )

    expect(screen.getByText('推杆四阶段')).toBeTruthy()
    expect(screen.getByText('推杆四维度')).toBeTruthy()
    expect(screen.getByText('钟摆稳定度')).toBeTruthy()
    expect(screen.getAllByText('最需改进').length).toBeGreaterThan(0)
    expect(screen.getByTestId('radar').textContent).toContain('瞄准准备')
  })
})
