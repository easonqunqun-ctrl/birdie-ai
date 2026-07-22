// 条件 map 条目（if (x != null) 'k': x）无法改写成 ?'k': x（? 作用于 key 非 value）。
// ignore_for_file: use_null_aware_elements
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../../core/api_client.dart';
import '../../core/env.dart';
import '../../core/storage.dart';
import '../models/analysis.dart';

/// 挥杆分析域仓库：对照 client/src/services/analysisService.ts。
/// 上传走同源 API multipart：POST /analyses/uploads/{upload_id}/video。
class AnalysisRepository {
  AnalysisRepository(this._api);
  final ApiClient _api;

  static const _apiTimeout = Duration(seconds: 120);
  static const _uploadTimeout = Duration(seconds: 300);

  Future<UploadToken> getUploadToken({
    required String fileName,
    required int fileSize,
    required String fileType,
    required double duration,
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/analyses/upload-token',
      data: {
        'file_name': fileName,
        'file_size': fileSize,
        'file_type': fileType,
        'duration': duration,
      },
      timeout: _apiTimeout,
    );
    return UploadToken.fromJson(data);
  }

  /// 同源 API 上传视频（multipart file 字段）。
  /// [onProgress] 回调 0-1；用 StreamedRequest 手动分块以拿到进度。
  Future<void> uploadVideo(
    String filePath,
    UploadToken token, {
    void Function(double progress)? onProgress,
  }) async {
    final base = Env.apiBase.replaceAll(RegExp(r'/$'), '');
    final uri = Uri.parse('$base/analyses/uploads/${token.uploadId}/video');
    final file = File(filePath);
    final total = await file.length();

    final request = http.MultipartRequest('POST', uri);
    final tk = AppStorage.instance.token;
    if (tk.isNotEmpty) request.headers['Authorization'] = 'Bearer $tk';

    // 手动构造带进度的 multipart file part
    var sent = 0;
    final fileStream = file.openRead().transform(
          StreamTransformer<List<int>, List<int>>.fromHandlers(
            handleData: (chunk, sink) {
              sent += chunk.length;
              if (total > 0) onProgress?.call(sent / total);
              sink.add(chunk);
            },
          ),
        );
    request.files.add(http.MultipartFile(
      'file',
      fileStream,
      total,
      filename: filePath.split('/').last,
      contentType: _contentTypeFor(filePath),
    ));

    final streamed = await request.send().timeout(_uploadTimeout);
    final res = await http.Response.fromStream(streamed);
    if (res.statusCode == 401) {
      throw ApiException(ApiErrorKind.httpUnauthorized, '登录已过期，请重新登录',
          status: 401);
    }
    if (res.statusCode != 200) {
      throw ApiException(ApiErrorKind.httpServerError,
          '上传失败（HTTP ${res.statusCode}）',
          status: res.statusCode);
    }
    try {
      final body = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      if (body['code'] != 0) {
        throw ApiException(
            ApiErrorKind.business, body['message']?.toString() ?? '上传失败');
      }
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(ApiErrorKind.badResponse, '上传响应格式错误');
    }
  }

  Future<CreateAnalysisResult> createAnalysis({
    required String uploadId,
    required String cameraAngle,
    required String clubType,
    String mode = 'full_swing',
    int? targetYardage,
    int? selectedSwingIndex,
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/analyses',
      data: {
        'upload_id': uploadId,
        'camera_angle': cameraAngle,
        'club_type': clubType,
        'mode': mode,
        if (targetYardage != null) 'target_yardage': targetYardage,
        if (selectedSwingIndex != null)
          'selected_swing_index': selectedSwingIndex,
      },
      timeout: _apiTimeout,
    );
    return CreateAnalysisResult.fromJson(data);
  }

  /// M7-13 · 多挥检测（上传完成后调用；失败由调用方降级直创任务）
  Future<DetectSwingsResult> detectSwings(String uploadId) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/analyses/uploads/$uploadId/detect-swings',
      data: const {},
      timeout: _apiTimeout,
    );
    return DetectSwingsResult.fromJson(data);
  }

  Future<AnalysisStatusInfo> getStatus(String analysisId) async {
    final data = await _api.get<Map<String, dynamic>>(
      '/analyses/$analysisId/status',
      timeout: _apiTimeout,
    );
    return AnalysisStatusInfo.fromJson(data);
  }

  Future<AnalysisReport> getReport(String analysisId) async {
    final path =
        analysisId == 'sample' ? '/analyses/sample' : '/analyses/$analysisId';
    final data = await _api.get<Map<String, dynamic>>(path, timeout: _apiTimeout);
    return AnalysisReport.fromJson(data);
  }

  Future<List<AnalysisListItem>> listAnalyses({
    int page = 1,
    int pageSize = 20,
    String? clubType,
  }) async {
    final qs = <String, String>{
      'page': '$page',
      'page_size': '$pageSize',
      if (clubType != null) 'club_type': clubType,
    };
    final query = qs.entries.map((e) => '${e.key}=${e.value}').join('&');
    final data =
        await _api.get<Map<String, dynamic>>('/analyses?$query');
    final items = (data['items'] as List?)
            ?.map((e) => AnalysisListItem.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [];
    return items;
  }

  /// 带分页信息的列表（total + paywall），对齐小程序 history。
  Future<AnalysisListPage> listAnalysesPage({
    int page = 1,
    int pageSize = 20,
  }) async {
    final data = await _api.get<Map<String, dynamic>>(
        '/analyses?page=$page&page_size=$pageSize');
    final items = (data['items'] as List?)
            ?.map((e) => AnalysisListItem.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const <AnalysisListItem>[];
    return AnalysisListPage(
      items: items,
      total: (data['total'] as num?)?.toInt() ?? items.length,
      page: (data['page'] as num?)?.toInt() ?? page,
      pageSize: (data['page_size'] as num?)?.toInt() ?? pageSize,
    );
  }

  Future<void> deleteAnalysis(String analysisId) =>
      _api.del('/analyses/$analysisId');

  MediaType _contentTypeFor(String path) {
    final lower = path.toLowerCase();
    if (lower.endsWith('.mov')) return MediaType('video', 'quicktime');
    return MediaType('video', 'mp4');
  }
}
