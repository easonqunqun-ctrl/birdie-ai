import { render, screen } from '@testing-library/react'
import EnvBadge from '@/components/EnvBadge'

describe('EnvBadge', () => {
  const g = globalThis as unknown as { APP_ENV: string; BUILD_MARKER?: string }
  const origEnv = g.APP_ENV
  const origMarker = g.BUILD_MARKER

  afterEach(() => {
    g.APP_ENV = origEnv
    g.BUILD_MARKER = origMarker
  })

  test('production → 不渲染', () => {
    g.APP_ENV = 'production'
    const { container } = render(<EnvBadge />)
    expect(container.firstChild).toBeNull()
  })

  test('test → 显示环境标签', () => {
    g.APP_ENV = 'test'
    g.BUILD_MARKER = ''
    render(<EnvBadge />)
    expect(screen.getByText('test')).toBeInTheDocument()
  })

  test('staging + BUILD_MARKER → 环境·hash', () => {
    g.APP_ENV = 'staging'
    g.BUILD_MARKER = 'staging@abc1234def+dirty built 2026-07-20 01:00 UTC'
    render(<EnvBadge />)
    expect(screen.getByText('staging·abc1234def')).toBeInTheDocument()
  })
})
