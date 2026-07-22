// 训练计划 DTO：对照 client/src/types/training.ts。

class TrainingTask {
  final String id;
  final String drillId;
  final String scheduledDate;
  final int sortOrder;
  final String status; // pending / completed
  final String? completedAt;
  final String? coachNote;

  const TrainingTask({
    required this.id,
    required this.drillId,
    required this.scheduledDate,
    this.sortOrder = 0,
    this.status = 'pending',
    this.completedAt,
    this.coachNote,
  });

  bool get isCompleted => status == 'completed';

  factory TrainingTask.fromJson(Map<String, dynamic> j) => TrainingTask(
        id: j['id']?.toString() ?? '',
        drillId: j['drill_id']?.toString() ?? '',
        scheduledDate: j['scheduled_date']?.toString() ?? '',
        sortOrder: (j['sort_order'] as num?)?.toInt() ?? 0,
        status: j['status']?.toString() ?? 'pending',
        completedAt: j['completed_at'] as String?,
        coachNote: j['coach_note'] as String?,
      );
}

class TrainingPlan {
  final String id;
  final String weekStart;
  final String weekEnd;
  final String? aiSummary;
  final int totalTasks;
  final int completedTasks;
  final List<TrainingTask> tasks;

  const TrainingPlan({
    required this.id,
    required this.weekStart,
    required this.weekEnd,
    this.aiSummary,
    this.totalTasks = 0,
    this.completedTasks = 0,
    this.tasks = const [],
  });

  factory TrainingPlan.fromJson(Map<String, dynamic> j) => TrainingPlan(
        id: j['id']?.toString() ?? '',
        weekStart: j['week_start']?.toString() ?? '',
        weekEnd: j['week_end']?.toString() ?? '',
        aiSummary: j['ai_summary'] as String?,
        totalTasks: (j['total_tasks'] as num?)?.toInt() ?? 0,
        completedTasks: (j['completed_tasks'] as num?)?.toInt() ?? 0,
        tasks: (j['tasks'] as List?)
                ?.map((e) => TrainingTask.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
      );
}

class UserClub {
  final String id;
  final String clubType;
  final String? nickname;
  final num? selfYardageM;
  final bool isActive;

  const UserClub({
    required this.id,
    required this.clubType,
    this.nickname,
    this.selfYardageM,
    this.isActive = true,
  });

  factory UserClub.fromJson(Map<String, dynamic> j) => UserClub(
        id: j['id']?.toString() ?? '',
        clubType: j['club_type']?.toString() ?? 'unknown',
        nickname: j['nickname'] as String?,
        selfYardageM: j['self_yardage_m'] as num?,
        isActive: j['is_active'] != false,
      );
}

class PracticeLogItem {
  final String? practiceDate;
  const PracticeLogItem({this.practiceDate});

  factory PracticeLogItem.fromJson(Map<String, dynamic> j) => PracticeLogItem(
        practiceDate: j['practice_date'] as String?,
      );
}

class AnalysisProgressPoint {
  final String analysisId;
  final String analyzedAt;
  final double overallScore;
  final Map<String, num>? phaseScores;

  const AnalysisProgressPoint({
    required this.analysisId,
    required this.analyzedAt,
    required this.overallScore,
    this.phaseScores,
  });

  factory AnalysisProgressPoint.fromJson(Map<String, dynamic> j) =>
      AnalysisProgressPoint(
        analysisId: j['analysis_id']?.toString() ?? '',
        analyzedAt: j['analyzed_at']?.toString() ?? '',
        overallScore: (j['overall_score'] as num?)?.toDouble() ?? 0,
        phaseScores: (j['phase_scores'] as Map?)?.map(
          (k, v) => MapEntry(k.toString(), v as num),
        ),
      );
}
