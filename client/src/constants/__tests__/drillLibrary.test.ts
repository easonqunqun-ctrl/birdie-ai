import { DRILL_CATALOG, getDrillDetail } from '../drillLibrary'

describe('drillLibrary · W26 库对齐', () => {
  it('DRILL_CATALOG 与后端 seed 同为 30 条', () => {
    expect(DRILL_CATALOG).toHaveLength(30)
  })

  it('0043/0044 新增短杆 drill 可解析', () => {
    const wrist = getDrillDetail('drill_wrist_lock_putt')
    expect(wrist.category).toBe('putting')
    expect(wrist.tips?.length).toBeGreaterThan(0)

    const aim = getDrillDetail('drill_string_line_putt')
    expect(aim.target_issue).toBe('putting_aim_off')
  })

  it('未知 drill_id 走兜底不抛错', () => {
    const fallback = getDrillDetail('drill_unknown_xyz')
    expect(fallback.name).toBe('drill_unknown_xyz')
    expect(fallback.steps.length).toBeGreaterThan(0)
  })
})
