import { render, screen } from '@testing-library/react'
import EnvBadge from '@/components/EnvBadge'

describe('EnvBadge', () => {
  const g = globalThis as unknown as { APP_ENV: string }
  const orig = g.APP_ENV

  afterEach(() => {
    g.APP_ENV = orig
  })

  test('production → 不渲染', () => {
    g.APP_ENV = 'production'
    const { container } = render(<EnvBadge />)
    expect(container.firstChild).toBeNull()
  })

  test('test → 显示环境标签', () => {
    g.APP_ENV = 'test'
    render(<EnvBadge />)
    expect(screen.getByText('test')).toBeInTheDocument()
  })
})
