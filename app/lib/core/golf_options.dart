// 高尔夫档案选项常量：对照 client/src/constants/golf.ts。
// 由 onboarding 与「编辑档案」共用，字面量/排序/文案须与小程序一致。

class LevelOption {
  final String value;
  final String label;
  final String desc;
  const LevelOption(this.value, this.label, this.desc);
}

class Option {
  final String value;
  final String label;
  const Option(this.value, this.label);
}

const levels = <LevelOption>[
  LevelOption('beginner', '初学者', '刚接触不到 1 年'),
  LevelOption('elementary', '初级', '1-3 年，差点 25+'),
  LevelOption('intermediate', '中级', '差点 10-25'),
  LevelOption('advanced', '高级', '差点 10 以下'),
];

const goals = <Option>[
  Option('distance', '提升距离'),
  Option('accuracy', '提升准度'),
  Option('short_game', '短杆球技'),
  Option('putting', '推杆技术'),
  Option('consistency', '一致性'),
];

const freqs = <Option>[
  Option('occasional', '偶尔'),
  Option('once', '每周 1 次'),
  Option('frequent', '每周 2-3 次'),
  Option('daily', '几乎每天'),
];

const maxGoals = 3;

const levelLabels = <String, String>{
  'beginner': '初学者',
  'elementary': '初级',
  'intermediate': '中级',
  'advanced': '高级',
};

const goalLabels = <String, String>{
  'distance': '提升距离',
  'accuracy': '提升准度',
  'short_game': '短杆球技',
  'putting': '推杆技术',
  'consistency': '一致性',
};

const freqLabels = <String, String>{
  'occasional': '偶尔',
  'once': '每周 1 次',
  'frequent': '每周 2-3 次',
  'daily': '几乎每天',
};
