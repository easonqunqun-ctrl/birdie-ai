/**
 * 训练打卡月历布局（Q-B3 / v1.1.0）
 *
 * 纯函数；输入 month=YYYY-MM 与 practice_logs 聚合 count，输出 6×7 网格。
 */

export interface PracticeCalendarCell {
  /** YYYY-MM-DD；padding 格为空串 */
  dateKey: string
  day: number
  count: number
  isToday: boolean
  inMonth: boolean
}

export interface PracticeCalendarGrid {
  monthKey: string
  /** 固定 6 行 × 7 列 */
  weeks: PracticeCalendarCell[][]
  monthTotal: number
}

const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日'] as const

export function practiceCalendarWeekdayLabels(): readonly string[] {
  return WEEKDAY_LABELS
}

/** 解析 YYYY-MM → { year, month }；非法返回 null */
export function parseMonthKey(monthKey: string): { year: number; month: number } | null {
  const m = monthKey.match(/^(\d{4})-(\d{2})$/)
  if (!m) return null
  const year = Number(m[1])
  const month = Number(m[2])
  if (!year || month < 1 || month > 12) return null
  return { year, month }
}

/** 本地 today → YYYY-MM-DD */
export function localDateKey(d: Date = new Date()): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function monthKeyNow(d: Date = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** 上/下月 monthKey */
export function shiftMonthKey(monthKey: string, delta: number): string {
  const parsed = parseMonthKey(monthKey)
  if (!parsed) return monthKeyNow()
  let { year, month } = parsed
  month += delta
  while (month < 1) {
    month += 12
    year -= 1
  }
  while (month > 12) {
    month -= 12
    year += 1
  }
  return `${year}-${String(month).padStart(2, '0')}`
}

/** 从 practice_logs 列表聚合 dateKey → count */
export function aggregatePracticeCounts(
  logs: { practice_date?: string | null }[],
): Map<string, number> {
  const counts = new Map<string, number>()
  for (const log of logs) {
    const key = (log.practice_date ?? '').slice(0, 10)
    if (!key) continue
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return counts
}

export function buildPracticeCalendarGrid(
  monthKey: string,
  counts: Map<string, number>,
  todayKey: string = localDateKey(),
): PracticeCalendarGrid {
  const parsed = parseMonthKey(monthKey)
  if (!parsed) {
    return { monthKey, weeks: [], monthTotal: 0 }
  }
  const { year, month } = parsed
  const first = new Date(year, month - 1, 1)
  const lastDay = new Date(year, month, 0).getDate()
  // 周一为 0（ISO 风格）
  const firstWeekday = (first.getDay() + 6) % 7

  let monthTotal = 0
  for (let day = 1; day <= lastDay; day += 1) {
    const dd = String(day).padStart(2, '0')
    const mm = String(month).padStart(2, '0')
    monthTotal += counts.get(`${year}-${mm}-${dd}`) ?? 0
  }

  const cells: PracticeCalendarCell[] = []
  for (let i = 0; i < firstWeekday; i += 1) {
    cells.push({ dateKey: '', day: 0, count: 0, isToday: false, inMonth: false })
  }
  for (let day = 1; day <= lastDay; day += 1) {
    const dd = String(day).padStart(2, '0')
    const mm = String(month).padStart(2, '0')
    const dateKey = `${year}-${mm}-${dd}`
    cells.push({
      dateKey,
      day,
      count: counts.get(dateKey) ?? 0,
      isToday: dateKey === todayKey,
      inMonth: true,
    })
  }
  while (cells.length % 7 !== 0) {
    cells.push({ dateKey: '', day: 0, count: 0, isToday: false, inMonth: false })
  }
  while (cells.length < 42) {
    cells.push({ dateKey: '', day: 0, count: 0, isToday: false, inMonth: false })
  }

  const weeks: PracticeCalendarCell[][] = []
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7))
  }
  return { monthKey, weeks, monthTotal }
}

export function formatMonthTitle(monthKey: string): string {
  const parsed = parseMonthKey(monthKey)
  if (!parsed) return monthKey
  return `${parsed.year}年${parsed.month}月`
}
