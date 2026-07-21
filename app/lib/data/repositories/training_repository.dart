// ignore_for_file: use_null_aware_elements
import '../../core/api_client.dart';
import '../models/training.dart';

/// 训练计划域仓库：对照 client/src/services/trainingService.ts。
class TrainingRepository {
  TrainingRepository(this._api);
  final ApiClient _api;

  /// 当前训练计划；无计划时返回 null。
  Future<TrainingPlan?> getCurrentPlan() async {
    final data =
        await _api.get<dynamic>('/users/me/training-plan/current');
    if (data is! Map<String, dynamic>) return null;
    return TrainingPlan.fromJson(data);
  }

  /// 完成打卡，返回连续打卡天数（后端 current_streak_days），失败/缺省为 null。
  Future<int?> completeTask(String taskId, {int? durationMinutes}) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/training-plan/tasks/$taskId/complete',
      data: {
        if (durationMinutes != null) 'duration_minutes': durationMinutes,
      },
    );
    return (data['current_streak_days'] as num?)?.toInt();
  }

  /// 从分析报告一键加入本周训练计划（后端幂等）。
  Future<void> addFromAnalysis(String analysisId) async {
    await _api.post<dynamic>('/training-plan/from-analysis/$analysisId');
  }
}
