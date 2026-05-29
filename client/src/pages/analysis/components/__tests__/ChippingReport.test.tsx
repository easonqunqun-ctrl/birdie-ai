import { render, screen } from '@testing-library/react'
import ChippingReport from '@/pages/analysis/components/ChippingReport'

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

describe('ChippingReport', () => {
  test('renders chipping phases and three feature dimensions', () => {
    render(
      <ChippingReport
        phaseScores={{
          setup: { score: 82, label: '瞄准准备', is_weakest: false },
          backswing: { score: 75, label: '上杆', is_weakest: true },
          impact: { score: 80, label: '击球', is_weakest: false },
          follow: { score: 85, label: '收杆', is_weakest: false },
        }}
        chippingFeatures={{
          half_swing_amplitude: { score: 78, label: '半挥幅度', is_weakest: true },
          face_open_angle: { score: 82, label: '杆面开角', is_weakest: false },
          contact_point_quality: { score: 80, label: '触球质量', is_weakest: false },
        }}
      />,
    )

    expect(screen.getByText('切杆四阶段')).toBeTruthy()
    expect(screen.getByText('切杆三维度')).toBeTruthy()
    expect(screen.getByText('半挥幅度')).toBeTruthy()
    expect(screen.getByTestId('radar').textContent).toContain('上杆')
  })
})
