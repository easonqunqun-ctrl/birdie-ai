import {
  isPromoFreeActive,
  isPromoFreeUntilActive,
  promoFreeBannerText,
  resolvePromoFreeStatus,
} from '@/utils/promoFree'

describe('promoFree', () => {
  beforeEach(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2026-06-20T12:00:00+08:00'))
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it('isPromoFreeUntilActive before end date', () => {
    expect(isPromoFreeUntilActive('2026-07-30')).toBe(true)
  })

  it('isPromoFreeUntilActive after end date', () => {
    jest.setSystemTime(new Date('2026-07-31T00:00:01+08:00'))
    expect(isPromoFreeUntilActive('2026-07-30')).toBe(false)
  })

  it('resolvePromoFreeStatus prefers user payload', () => {
    const status = resolvePromoFreeStatus({
      promo_free: { active: true, until: '2026-07-30', message: '后端文案' },
    } as never)
    expect(status?.message).toBe('后端文案')
  })

  it('promoFreeBannerText formats until date', () => {
    expect(
      promoFreeBannerText({
        promo_free: { active: true, until: '2026-07-30', message: null },
      } as never),
    ).toBe('公测免费至 7 月 30 日')
  })

  it('isPromoFreeActive false when inactive', () => {
    expect(isPromoFreeActive({ promo_free: { active: false, until: null, message: null } } as never)).toBe(false)
  })
})
