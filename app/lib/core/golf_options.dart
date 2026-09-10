// 高尔夫档案选项常量：对照 client/src/constants/golf.ts。
// 由 onboarding 与「编辑档案」共用，value 与小程序一致；展示文案走 l10n。

import '../l10n/app_localizations.dart';

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

String localizedLevel(AppLocalizations l10n, String? value) {
  return switch (value) {
    'beginner' => l10n.levelBeginner,
    'elementary' => l10n.levelElementary,
    'intermediate' => l10n.levelIntermediate,
    'advanced' => l10n.levelAdvanced,
    _ => l10n.notSet,
  };
}

String localizedGoal(AppLocalizations l10n, String value) {
  return switch (value) {
    'distance' => l10n.goalDistance,
    'accuracy' => l10n.goalAccuracy,
    'short_game' => l10n.goalShortGame,
    'putting' => l10n.goalPutting,
    'consistency' => l10n.goalConsistency,
    _ => value,
  };
}

String localizedFreq(AppLocalizations l10n, String? value) {
  return switch (value) {
    'occasional' => l10n.freqOccasional,
    'once' => l10n.freqOnce,
    'frequent' => l10n.freqFrequent,
    'daily' => l10n.freqDaily,
    _ => l10n.notSet,
  };
}

String localizedWeekday(AppLocalizations l10n, int weekday) {
  return switch (weekday) {
    1 => l10n.weekdayMon,
    2 => l10n.weekdayTue,
    3 => l10n.weekdayWed,
    4 => l10n.weekdayThu,
    5 => l10n.weekdayFri,
    6 => l10n.weekdaySat,
    _ => l10n.weekdaySun,
  };
}

String localizedLevelDesc(AppLocalizations l10n, String value) {
  return switch (value) {
    'beginner' => l10n.levelBeginnerDesc,
    'elementary' => l10n.levelElementaryDesc,
    'intermediate' => l10n.levelIntermediateDesc,
    'advanced' => l10n.levelAdvancedDesc,
    _ => '',
  };
}
