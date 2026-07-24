import '../../core/api_client.dart';
import '../models/content.dart';

/// 长尾内容域仓库：对照 coursesService / prosService / meetupEventService。
/// 均受后端 PHASE2_* 灰度控制，未开时返回 404；页面以空态兜底。
class ContentRepository {
  ContentRepository(this._api);
  final ApiClient _api;

  Future<List<Course>> listCourses() async {
    final data = await _api.get<dynamic>('/courses');
    if (data is! List) return const [];
    return data
        .whereType<Map>()
        .map((e) => Course.fromJson(e.cast<String, dynamic>()))
        .toList();
  }

  Future<List<ProPlayer>> listPros() async {
    final data = await _api.get<dynamic>('/pros');
    if (data is! List) return const [];
    return data
        .whereType<Map>()
        .map((e) => ProPlayer.fromJson(e.cast<String, dynamic>()))
        .toList();
  }

  /// M12-04 · 为分析报告匹配职业镜头。灰度关闭时后端 404。
  Future<ProMatchResult> matchForAnalysis(
    String analysisId, {
    int limit = 5,
    bool record = false,
  }) async {
    final path =
        '/analyses/$analysisId/pro-matches?limit=$limit&record=${record ? 'true' : 'false'}';
    final data = await _api.get<Map<String, dynamic>>(path);
    return ProMatchResult.fromJson(data);
  }

  Future<List<MeetupEvent>> listMeetups() async {
    final data = await _api.get<Map<String, dynamic>>('/meetups/events');
    return (data['items'] as List?)
            ?.whereType<Map>()
            .map((e) => MeetupEvent.fromJson(e.cast<String, dynamic>()))
            .toList() ??
        const [];
  }
}
