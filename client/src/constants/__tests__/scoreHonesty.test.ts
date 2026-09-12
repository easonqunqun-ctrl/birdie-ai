import {
  SCORE_HONESTY_FOOTNOTE,
  SCORE_HONESTY_GUIDE_BODY,
  SCORE_HONESTY_GUIDE_TITLE,
  scoreHonestyCopyIsHonest,
} from '@/constants/scoreHonesty'

describe('PP-16 scoreHonesty', () => {
  test('脚注承认手腕推算，且不含追踪伪装', () => {
    expect(SCORE_HONESTY_FOOTNOTE).toMatch(/手腕/)
    expect(SCORE_HONESTY_FOOTNOTE).toMatch(/推算/)
    expect(SCORE_HONESTY_FOOTNOTE).toMatch(/不是杆头或球的追踪/)
    expect(scoreHonestyCopyIsHonest(SCORE_HONESTY_FOOTNOTE)).toBe(true)
    expect(scoreHonestyCopyIsHonest(SCORE_HONESTY_GUIDE_BODY)).toBe(true)
  })

  test('分数说明标题存在', () => {
    expect(SCORE_HONESTY_GUIDE_TITLE).toBe('杆面和触球')
  })

  test('伪装追踪句应判不诚实', () => {
    expect(scoreHonestyCopyIsHonest('系统已识别杆面开闭')).toBe(false)
    expect(scoreHonestyCopyIsHonest('已追踪击球厚薄')).toBe(false)
  })
})
