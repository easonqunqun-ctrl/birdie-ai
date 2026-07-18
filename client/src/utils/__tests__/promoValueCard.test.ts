import { shouldShowPromoValueCardPure } from '@/utils/promoValueCard'

describe('shouldShowPromoValueCardPure', () => {
  it('hides when promo inactive', () => {
    expect(
      shouldShowPromoValueCardPure({
        promoActive: false,
        todayDateKey: '2026-07-18',
        lastShownDateKey: null,
      }),
    ).toBe(false)
  })

  it('shows once per day', () => {
    expect(
      shouldShowPromoValueCardPure({
        promoActive: true,
        todayDateKey: '2026-07-18',
        lastShownDateKey: null,
      }),
    ).toBe(true)
    expect(
      shouldShowPromoValueCardPure({
        promoActive: true,
        todayDateKey: '2026-07-18',
        lastShownDateKey: '2026-07-18',
      }),
    ).toBe(false)
    expect(
      shouldShowPromoValueCardPure({
        promoActive: true,
        todayDateKey: '2026-07-19',
        lastShownDateKey: '2026-07-18',
      }),
    ).toBe(true)
  })
})
