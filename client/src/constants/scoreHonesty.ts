/**
 * PP-16：杆面 / 触球诚实话术（不上 M7-09 追踪）。
 * 真源：docs/release-notes/product-2week-close-2026-09-12.md §三
 * 须与 docs/20 §4.3、docs/09 §8.6、App `score_honesty.dart` 同义。
 */

/** 报告页综合分附近一行脚注 */
export const SCORE_HONESTY_FOOTNOTE =
  '杆面和触球目前由手腕轨迹推算，不是杆头或球的追踪。请当作参考，不要当成杆面开闭或击球厚薄的结论。想提高可信度：侧机位、全身入镜、光线够。'

/** 分数说明页小节标题 */
export const SCORE_HONESTY_GUIDE_TITLE = '杆面和触球'

/** 分数说明页 / 客服可复制段（与脚注同义，可稍完整） */
export const SCORE_HONESTY_GUIDE_BODY = SCORE_HONESTY_FOOTNOTE

const FORBIDDEN_CLAIMS = ['已识别杆面', '已追踪击球', '已追踪杆头', '已追踪球'] as const

/** 契约：对外文案不得伪装成杆头/球追踪 */
export function scoreHonestyCopyIsHonest(text: string): boolean {
  return FORBIDDEN_CLAIMS.every((phrase) => !text.includes(phrase))
}
