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

// 13 个 drill：覆盖 docs/14 附录 A 映射表里全部 issue。drill_id 与
// `ai_engine/app/mock_pipeline.py::DRILL_TEMPLATES` 保持同步；增删时两边必须一起改。
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
    drill_id: 'drill_impact_bag',
    name: '击球包练习',
    target_issue: 'casting',
    description: '强化击球位置的手腕前倾与身体连动，修正抛杆。',
    duration_minutes: 10,
    sets: 3,
    reps: 10,
    difficulty: '进阶',
    equipment: ['击球包或厚枕头'],
    steps: [
      '将击球包（或厚枕头）放在球位前方',
      '用半挥杆慢速击打，手腕保持前倾、杆头贴近身体',
      '记录手腕第一次"解锁"的感觉',
      '10 次为一组，共 3 组',
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
    drill_id: 'drill_inside_path',
    name: '内侧下杆路径练习',
    target_issue: 'over_the_top',
    description: '用地上放杆引导下杆路径从内侧进入，消除外上内下。',
    duration_minutes: 15,
    sets: 3,
    reps: 10,
    difficulty: '进阶',
    equipment: ['练习杆 × 1'],
    steps: [
      '在球位正后方 30cm 平行放一支练习杆',
      '上杆后刻意让下杆杆头沿练习杆内侧通过',
      '感受上半身被动、下半身主动的发力顺序',
      '每组 10 次，共 3 组',
    ],
  },
  {
    drill_id: 'drill_wall_butt',
    name: '臀贴墙练习',
    target_issue: 'early_extension',
    description: '保持臀部与墙接触，避免下杆髋部前移（提前伸展 / 反向脊柱通用）。',
    duration_minutes: 10,
    sets: 3,
    reps: 10,
    difficulty: '入门',
    steps: [
      '背对墙站立，臀部轻贴墙面',
      '做上杆到下杆的镜像动作，臀部始终不离开墙',
      '感受脊柱角度在整个过程中保持不变',
      '10 次为一组，共 3 组',
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
  {
    drill_id: 'drill_mirror_spine',
    name: '镜前脊柱角度练习',
    target_issue: 'loss_of_posture',
    description: '借助镜子观察整挥中脊柱角是否恒定。',
    duration_minutes: 10,
    sets: 2,
    reps: 10,
    difficulty: '入门',
    equipment: ['落地镜'],
    steps: [
      '面对落地镜做空挥',
      '观察从 setup 到 impact 脊柱前倾角的变化',
      '调整节奏直到差异 < 5°',
      '每组 10 次，共 2 组',
    ],
  },
  {
    drill_id: 'drill_weight_shift',
    name: '重心转移节奏练习',
    target_issue: 'hanging_back',
    description: '通过节奏口令建立"后-前-后"的重心流，修正留身。',
    duration_minutes: 15,
    sets: 3,
    reps: 10,
    difficulty: '入门',
    steps: [
      '站姿自然，口令"后、前、收"配合上杆 / 下杆 / 收杆',
      '收杆时感受 80% 重心在前脚',
      '对镜子检查完成姿势',
      '每组 10 次，共 3 组',
    ],
  },
  {
    drill_id: 'drill_backswing_stop',
    name: '上杆截停练习',
    target_issue: 'over_rotation',
    description: '防止过度转肩，控制上杆幅度。',
    duration_minutes: 10,
    sets: 3,
    reps: 10,
    difficulty: '入门',
    steps: [
      '上杆到杆接近水平就停住，保持 2 秒',
      '确认肩转约 90°，再开始下杆',
      '体会"到位就停"的节奏',
      '每组 10 次，共 3 组',
    ],
  },
  {
    drill_id: 'drill_shoulder_turn',
    name: '充分转肩练习',
    target_issue: 'under_rotation',
    description: '强化上杆期充分转肩，提升力量传递。',
    duration_minutes: 10,
    sets: 3,
    reps: 20,
    difficulty: '入门',
    steps: [
      '双手交叉抱肩',
      '做上半身旋转，直到左肩触到下巴',
      '保持髋部角度基本不变',
      '20 次为一组，共 3 组',
    ],
  },
  {
    drill_id: 'drill_plane_board',
    name: '挥杆平面板练习',
    target_issue: 'flat_shoulder',
    description: '借助倾斜板（或墙角）修正肩平面角。',
    duration_minutes: 15,
    sets: 3,
    reps: 10,
    difficulty: '进阶',
    equipment: ['练习板 / 厚枕头'],
    steps: [
      '在挥杆轨迹一侧斜放练习板 / 枕头',
      '上杆 / 下杆沿板面移动，既不过高也不过低',
      '感受杆头始终在肩平面上',
      '每组 10 次，共 3 组',
    ],
  },
  {
    drill_id: 'drill_alignment_stick',
    name: '瞄准杆站位练习',
    target_issue: 'open_stance',
    description: '用瞄准杆纠正站位与目标线的夹角。',
    duration_minutes: 5,
    sets: 2,
    reps: 10,
    difficulty: '入门',
    equipment: ['瞄准杆 × 1'],
    steps: [
      '在球位前方 2m 放置瞄准杆指向目标',
      '双脚、双膝、肩线都与瞄准杆平行',
      '检查自身影子 / 镜子里的角度',
      '每组 10 次 setup 练习，共 2 组',
    ],
  },
  {
    drill_id: 'drill_grip_checkpoint',
    name: '握杆检查点练习',
    target_issue: 'grip_weak',
    description: '按照标准握杆法复位左右手位置。',
    duration_minutes: 5,
    sets: 1,
    reps: 5,
    difficulty: '入门',
    steps: [
      '左手握杆，确认看到 2-3 颗指关节',
      '右手叠握，V 字指向右肩',
      '保持握杆压力 4/10',
      '练习 5 次，每次保持 10 秒',
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
