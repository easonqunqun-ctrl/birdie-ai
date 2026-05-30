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
  /** 教练提示（W26 · 可选） */
  tips?: string[]
  /** 难度（前端卡片右上角徽章） */
  difficulty: '入门' | '进阶' | '高级'
  /** M10-04：训练类目 */
  category?: 'full_swing' | 'putting' | 'chipping' | 'short_game' | 'general'
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
  {
    drill_id: 'drill_one_hand_putt',
    name: '单手推杆练习',
    target_issue: 'putting_unstable_pendulum',
    category: 'putting',
    description: '强化肩部钟摆主导，减少手腕独立发力。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '入门',
    tips: ['握压约 3/10，避免手指单独发力', '推完停留 1 秒再抬头看球线'],
    steps: ['非主导手背后', '主导手推 10 球', '关注肩臂一体'],
  },
  {
    drill_id: 'drill_gate_putt',
    name: '门型推杆练习',
    target_issue: 'putting_face_open',
    category: 'putting',
    description: '用 tees 做门型，约束杆头路径与杆面方正。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '入门',
    steps: ['球两侧插 tee', '推杆通过门型', '逐渐缩短门宽'],
  },
  {
    drill_id: 'drill_distance_ladder',
    name: '推杆距离梯',
    target_issue: 'putting_rushed_tempo',
    category: 'putting',
    description: '3/6/9 米递进，训练节奏与距离感。',
    duration_minutes: 20,
    sets: 1,
    difficulty: '进阶',
    steps: ['标记 3 个距离', '同一节奏各推 5 球', '记录落点'],
  },
  {
    drill_id: 'drill_eyes_closed_putt',
    name: '闭眼推杆',
    target_issue: 'putting_head_moved',
    category: 'putting',
    description: '减少视觉依赖，稳定头部与钟摆感。',
    duration_minutes: 10,
    sets: 3,
    difficulty: '入门',
    steps: ['1 米起推', '闭眼完成', '逐步加长'],
  },
  {
    drill_id: 'drill_clock_putt',
    name: '钟面推杆',
    target_issue: 'putting_unstable_pendulum',
    category: 'putting',
    description: '洞周多点推杆，练稳定度与读线。',
    duration_minutes: 18,
    sets: 1,
    difficulty: '进阶',
    steps: ['洞周标 4-6 点', '每点 3 球', '换点继续'],
  },
  {
    drill_id: 'drill_chip_land_spot',
    name: '切杆落点练习',
    target_issue: 'chipping_chunked',
    category: 'chipping',
    description: '先控落点再滚，建立触球前规划。',
    duration_minutes: 15,
    sets: 4,
    difficulty: '入门',
    steps: ['选落点圈', '切到落点停', '记录过/短'],
  },
  {
    drill_id: 'drill_low_runner',
    name: '低滚切杆',
    target_issue: 'chipping_scoop',
    category: 'chipping',
    description: '杆身前倾、短幅度，练低弹道滚进。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '进阶',
    steps: ['球位偏后', '杆身前倾', '短切低滚'],
  },
  {
    drill_id: 'drill_hinge_chip',
    name: '铰链切杆',
    target_issue: 'chipping_decel',
    category: 'chipping',
    description: '上杆小铰链、下杆加速通过球。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '进阶',
    steps: ['上杆腕铰链', '下杆加速', '短收送杆'],
  },
  {
    drill_id: 'drill_mirror_setup',
    name: '镜子站位练习',
    target_issue: 'loss_of_posture',
    category: 'full_swing',
    description: '对照镜子校正站姿与脊柱角。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '入门',
    steps: ['侧对镜子', '检查脊柱角', '半挥保持'],
  },
  {
    drill_id: 'drill_feet_together',
    name: '并脚平衡挥杆',
    target_issue: 'sway_slide',
    category: 'full_swing',
    description: '缩小支撑面，强化挥杆平衡。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '入门',
    steps: ['双脚并拢', '7 号铁半挥', '保持稳定'],
  },
  {
    drill_id: 'drill_pause_top',
    name: '顶点停顿练习',
    target_issue: 'over_rotation',
    category: 'full_swing',
    description: '上杆顶点多停 1 秒，改善转换顺序。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '进阶',
    steps: ['到顶停 1 秒', '再下杆', '半速重复'],
  },
  {
    drill_id: 'drill_step_through',
    name: '迈步送杆练习',
    target_issue: 'early_extension',
    category: 'full_swing',
    description: '送杆时迈步，强化重心转移。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '进阶',
    steps: ['正常上杆', '击球后迈步', '10 球一组'],
  },
  {
    drill_id: 'drill_wrist_lock_putt',
    name: '锁腕推杆',
    target_issue: 'putting_wrist_hinge',
    category: 'putting',
    description: '固定手腕角度，让肩部钟摆主导推击。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '入门',
    tips: ['可在推杆握把处贴胶带作手腕角度参照', '若球左右乱飞，先缩短距离再恢复'],
    steps: ['短推 1 米，手腕角度保持不变', '推击时只动肩臂', '每组 10 球记录偏离'],
  },
  {
    drill_id: 'drill_backstroke_pause',
    name: '回摆停顿推杆',
    target_issue: 'putting_decel_stroke',
    category: 'putting',
    description: '回摆到位后短暂停顿，再加速通过球。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '进阶',
    tips: ['停顿是为了确认回摆长度，不是刻意减速击球', '送杆长度应与回摆大致对称'],
    steps: ['上杆到舒适幅度后停 0.5 秒', '下杆加速通过球', '同距离推 10 球'],
  },
  {
    drill_id: 'drill_alignment_chip',
    name: '对准线切杆',
    target_issue: 'chipping_alignment_off',
    category: 'chipping',
    description: '用地面参照线校正脚线、球位与目标线。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '入门',
    tips: ['先练方向再练距离', '杆面与目标线垂直时初始方向更稳'],
    steps: ['地面贴杆作目标线', '脚线与目标线平行', '切 10 球观察方向'],
  },
  {
    drill_id: 'drill_accelerate_through',
    name: '加速通过切杆',
    target_issue: 'chipping_decel',
    category: 'chipping',
    description: '强调触球后杆头仍向目标加速，避免减速或挑球。',
    duration_minutes: 15,
    sets: 3,
    difficulty: '进阶',
    tips: ['减速击球常伴随挑球，先练低弹道滚进', '想象杆头要「穿过」球而非「舀」球'],
    steps: ['上杆至腰高以内', '触球后杆头向目标加速', '送杆时胸朝向目标'],
  },
  {
    drill_id: 'drill_string_line_putt',
    name: '绳线瞄准推杆',
    target_issue: 'putting_aim_off',
    category: 'putting',
    description: '用地面绳线校准推杆线与目标线，减少瞄准偏差。',
    duration_minutes: 12,
    sets: 3,
    difficulty: '入门',
    tips: ['先练 1 米直推再加长', '杆头路径比杆面更重要时，先对齐脚线与目标线'],
    steps: ['洞与球位之间拉绳作目标线', '推杆头沿目标线通过', '同距离推 10 球记录偏离'],
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

/** 教练派发作业等场景使用的静态动作列表（与后端 seed 对齐） */
export const DRILL_CATALOG: readonly DrillDetail[] = DRILLS
