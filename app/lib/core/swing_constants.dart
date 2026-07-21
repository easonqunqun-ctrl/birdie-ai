import 'package:flutter/material.dart';

/// 挥杆 6 阶段与评分分级常量：对照
/// client/src/constants/phaseLabels.ts + scoreLevel.ts。

const List<String> kPhaseOrder = [
  'setup',
  'backswing',
  'top',
  'downswing',
  'impact',
  'follow_through',
];

const Map<String, String> kPhaseLabel = {
  'setup': '站位',
  'backswing': '上杆',
  'top': '顶点',
  'downswing': '下杆',
  'impact': '击球',
  'follow_through': '收杆',
};

const Map<String, String> kPhaseFullLabel = {
  'setup': '站位准备',
  'backswing': '上杆轨迹',
  'top': '顶点位置',
  'downswing': '下杆转换',
  'impact': '击球触球',
  'follow_through': '收杆平衡',
};

const Map<String, Color> kPhaseColor = {
  'setup': Color(0xFF94A3B8),
  'backswing': Color(0xFF60A5FA),
  'top': Color(0xFFA78BFA),
  'downswing': Color(0xFFF472B6),
  'impact': Color(0xFFF97316),
  'follow_through': Color(0xFFC9A227),
};

class ScoreLevelMeta {
  final String label;
  final String caption;
  final Color color;
  final Color textColor;
  final String emoji;
  const ScoreLevelMeta({
    required this.label,
    required this.caption,
    required this.color,
    required this.textColor,
    required this.emoji,
  });
}

const Map<String, ScoreLevelMeta> kScoreLevelMeta = {
  'excellent': ScoreLevelMeta(
    label: '专业水准',
    caption: '非常棒，这一杆接近职业水平',
    color: Color(0xFFC9A227),
    textColor: Color(0xFF0F1535),
    emoji: '🏆',
  ),
  'great': ScoreLevelMeta(
    label: '进阶球员',
    caption: '稳定输出的挥杆，继续保持',
    color: Color(0xFF1A237E),
    textColor: Colors.white,
    emoji: '⛳️',
  ),
  'good': ScoreLevelMeta(
    label: '良好',
    caption: '基础不错，还有打磨空间',
    color: Color(0xFF3B82F6),
    textColor: Colors.white,
    emoji: '👍',
  ),
  'fair': ScoreLevelMeta(
    label: '及格',
    caption: '方向对了，把问题一个个解决',
    color: Color(0xFFF59E0B),
    textColor: Colors.white,
    emoji: '💪',
  ),
  'needs_improvement': ScoreLevelMeta(
    label: '待改进',
    caption: '放心，按建议练一周会有明显进步',
    color: Color(0xFFEF4444),
    textColor: Colors.white,
    emoji: '📈',
  ),
};

String? scoreLevelFromScore(num? score) {
  if (score == null) return null;
  if (score >= 90) return 'excellent';
  if (score >= 80) return 'great';
  if (score >= 70) return 'good';
  if (score >= 60) return 'fair';
  return 'needs_improvement';
}

const Map<String, String> kSeverityLabel = {
  'high': '严重',
  'medium': '中等',
  'low': '轻微',
};
