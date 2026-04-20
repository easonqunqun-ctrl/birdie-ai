/**
 * 训练动作库（drill library）
 *
 * 设计说明：
 *   - 后端 `AnalysisRecommendation` 只持久化 `drill_id / target_issue / sort_order`；
 *     drill 的名字、步骤、时长等详细信息属于"静态业务数据"，不随每次分析复写。
 *   - 所以前端内置一个映射表按 drill_id 查详情，渲染训练建议卡片。
 *   - 数据来源：`ai_engine/app/mock_pipeline.py::DRILL_TEMPLATES`（完整镜像）+
 *     一个 fallback，用于后端/AI 返回了未登记的 drill_id 时不至于 crash。
 *   - 后续如果真·drill 库升级（W5 训练计划），再把本文件改成远程拉取的 mini-cdn 结构。
 */

export interface DrillDetail {
  drill_id: string
  /** 中文名 */
  name: string
  /** 适合解决的问题 type（对应 IssueItem.type） */
  target_issue: string
  /** 简介（一句话说清楚这个动作干啥） */
  description: string
  /** 单次训练时长（分钟） */
  duration_minutes: number
  /** 组数 */
  sets: number
  /** 每组次数（可选） */
  reps?: number
  /** 步骤（有序） */
  steps: string[]
  /** 难度（前端卡片右上角徽章） */
  difficulty: '入门' | '进阶' | '高级'
  /** 需要的道具（可为空） */
  equipment?: string[]
}

const DRILLS: DrillDetail[] = [
  {
    drill_id: 'drill_towel_arm',
    name: '毛巾夹臂练习',
    target_issue: 'casting',
    description: '修复下杆时过早释放手腕，找到"双臂和身体一起走"的感觉。',
    duration_minutes: 15,
    sets: 3,
    reps: 10,
    difficulty: '入门',
    equipment: ['小毛巾 × 1'],
    steps: [
      '取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）',
      '做半挥杆练习，保持毛巾不掉落',
      '感受双臂与身体的连接感',
      '逐渐加大挥杆幅度到全挥',
      '每组 10 次挥杆，共 3 组，组间休息 30 秒',
    ],
  },
  {
    drill_id: 'drill_half_swing',
    name: '半挥杆节奏练习',
    target_issue: 'over_the_top',
    description: '建立"从内侧下杆"的路径感，缓解由外到内的击球问题。',
    duration_minutes: 20,
    sets: 5,
    reps: 10,
    difficulty: '入门',
    equipment: ['7 号铁 × 1'],
    steps: [
      '采用 7 号铁，站姿正常',
      '上杆只到水平位置（杆与地面平行）',
      '缓慢下杆，感受杆头从内侧进入击球区',
      '击球后跟进至同样高度',
      '每组 10 次，共 5 组，全程节奏 3:1',
    ],
  },
  {
    drill_id: 'drill_hip_rotation',
    name: '髋部旋转练习',
    target_issue: 'sway_slide',
    description: '纠正侧移，建立髋部以脊柱为轴的"旋转"而非"平移"感。',
    duration_minutes: 15,
    sets: 3,
    reps: 30,
    difficulty: '入门',
    steps: [
      '双脚与肩同宽，将球杆横放在髋部前',
      '保持上身静止，缓慢左右旋转髋部',
      '感受髋部以脊柱为轴的旋转',
      '每次旋转幅度从小到大',
      '30 次为一组，共 3 组',
    ],
  },
]

const DRILL_MAP: Record<string, DrillDetail> = DRILLS.reduce(
  (acc, d) => {
    acc[d.drill_id] = d
    return acc
  },
  {} as Record<string, DrillDetail>,
)

/** 兜底 drill：真实返回了未登记 ID 时展示，保证页面不崩。 */
const DRILL_FALLBACK: DrillDetail = {
  drill_id: 'drill_generic',
  name: '动作练习',
  target_issue: 'general',
  description: '教练推荐的针对性训练动作',
  duration_minutes: 15,
  sets: 3,
  difficulty: '入门',
  steps: ['按照教练建议完成该动作', '每次 15 分钟，每周 3 次'],
}

export function getDrillDetail(drillId: string): DrillDetail {
  return DRILL_MAP[drillId] ?? { ...DRILL_FALLBACK, drill_id: drillId, name: drillId }
}
