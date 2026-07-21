// 分析选项与校验常量：对照 client/src/types/analysis.ts 尾部映射。

const cameraAngleLabels = <String, String>{
  'face_on': '正面（Face-On）',
  'down_the_line': '侧面（Down-the-Line）',
};

const cameraAngleDesc = <String, String>{
  'face_on': '站在球员正对面拍摄，看挥杆平面与重心',
  'down_the_line': '沿击球方向延长线拍摄，看挥杆轨迹',
};

const clubTypeLabels = <String, String>{
  'driver': '1 号木（Driver）',
  'fairway_wood': '球道木',
  'iron_3': '3 号铁',
  'iron_4': '4 号铁',
  'iron_5': '5 号铁',
  'iron_6': '6 号铁',
  'iron_7': '7 号铁',
  'iron_8': '8 号铁',
  'iron_9': '9 号铁',
  'wedge': '挖起杆（Wedge）',
  'putter': '推杆（Putter）',
  'unknown': '其他 / 不确定',
};

class ClubGroup {
  final String title;
  final List<String> items;
  const ClubGroup(this.title, this.items);
}

const clubTypeGroups = <ClubGroup>[
  ClubGroup('木杆', ['driver', 'fairway_wood']),
  ClubGroup('铁杆', ['iron_3', 'iron_5', 'iron_7', 'iron_9']),
  ClubGroup('其他', ['wedge', 'putter', 'unknown']),
];

// 视频约束（VIDEO_CONSTRAINTS）
const kMinDurationSeconds = 2;
const kMaxDurationSeconds = 30;
const kMaxSizeBytes = 100 * 1024 * 1024;
const kAcceptedExtensions = ['mp4', 'mov'];

const scoreLevelLabels = <String, String>{
  'excellent': '卓越',
  'great': '优秀',
  'good': '良好',
  'fair': '尚可',
  'needs_improvement': '待提升',
};
