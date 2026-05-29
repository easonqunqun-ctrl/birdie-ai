import { formatCertificateIssuedAt, STAGE_TITLES } from '@/utils/certificateLayout'

describe('certificateLayout', () => {
  test('formatCertificateIssuedAt formats ISO date', () => {
    expect(formatCertificateIssuedAt('2026-05-29T08:00:00Z')).toMatch(/2026年05月/)
  })

  test('STAGE_TITLES has seven stages', () => {
    expect(Object.keys(STAGE_TITLES)).toHaveLength(7)
  })
})
