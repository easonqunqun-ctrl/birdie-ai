import 'dart:async';
import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../data/models/analysis.dart';
import '../../data/repositories/analysis_repository.dart';

enum AnalysisPhase { idle, uploading, creating, processing, completed, failed }

/// 挥杆分析编排：对照 client/src/store/analysisStore.ts。
/// 流程：getUploadToken → uploadVideo → createAnalysis → 轮询 getStatus → 报告就绪。
class AnalysisController extends ChangeNotifier {
  AnalysisController(this._repo);
  final AnalysisRepository _repo;

  AnalysisPhase _phase = AnalysisPhase.idle;
  double _uploadProgress = 0;
  int _stageProgress = 0;
  String? _stage;
  int? _remainingSeconds;
  String? _analysisId;
  String? _error;

  AnalysisPhase get phase => _phase;
  double get uploadProgress => _uploadProgress;
  int get stageProgress => _stageProgress;
  String? get stage => _stage;
  int? get remainingSeconds => _remainingSeconds;
  String? get analysisId => _analysisId;
  String? get error => _error;
  bool get busy =>
      _phase == AnalysisPhase.uploading ||
      _phase == AnalysisPhase.creating ||
      _phase == AnalysisPhase.processing;

  Timer? _poll;

  void reset() {
    _poll?.cancel();
    _phase = AnalysisPhase.idle;
    _uploadProgress = 0;
    _stageProgress = 0;
    _stage = null;
    _remainingSeconds = null;
    _analysisId = null;
    _error = null;
    notifyListeners();
  }

  /// 启动一次分析。返回 analysisId（用于导航到等待页）；失败抛异常。
  Future<String> startAnalysis({
    required String filePath,
    required int fileSize,
    required double duration,
    required String cameraAngle,
    required String clubType,
    String mode = 'full_swing',
  }) async {
    _error = null;
    _uploadProgress = 0;
    _phase = AnalysisPhase.uploading;
    notifyListeners();

    try {
      final fileName = filePath.split('/').last;
      final fileType =
          fileName.toLowerCase().endsWith('.mov') ? 'video/quicktime' : 'video/mp4';
      final token = await _repo.getUploadToken(
        fileName: fileName,
        fileSize: fileSize,
        fileType: fileType,
        duration: duration,
      );

      await _repo.uploadVideo(filePath, token, onProgress: (p) {
        _uploadProgress = p.clamp(0, 1);
        notifyListeners();
      });

      _phase = AnalysisPhase.creating;
      notifyListeners();
      final created = await _repo.createAnalysis(
        uploadId: token.uploadId,
        cameraAngle: cameraAngle,
        clubType: clubType,
        mode: mode,
      );
      _analysisId = created.analysisId;
      _remainingSeconds = created.estimatedSeconds;
      _phase = AnalysisPhase.processing;
      notifyListeners();
      return created.analysisId;
    } catch (e) {
      _phase = AnalysisPhase.failed;
      _error = describeRequestFailure(e).fatalMessage;
      notifyListeners();
      rethrow;
    }
  }

  /// 轮询状态直到 completed / failed。完成回调 onDone(analysisId)。
  void startPolling(String analysisId,
      {required void Function() onCompleted,
      required void Function(String message) onFailed}) {
    _poll?.cancel();
    _analysisId = analysisId;
    _phase = AnalysisPhase.processing;
    notifyListeners();

    Future<void> tick() async {
      try {
        final st = await _repo.getStatus(analysisId);
        _stage = st.stage;
        _stageProgress = st.stageProgress;
        _remainingSeconds = st.estimatedRemainingSeconds;
        if (st.isCompleted) {
          _poll?.cancel();
          _phase = AnalysisPhase.completed;
          notifyListeners();
          onCompleted();
          return;
        }
        if (st.isFailed) {
          _poll?.cancel();
          _phase = AnalysisPhase.failed;
          _error = st.error?.message ?? '分析失败，请重试';
          notifyListeners();
          onFailed(_error!);
          return;
        }
        notifyListeners();
      } on ApiException catch (e) {
        // 轮询期弱网/5xx 不立即失败，继续下次；401 才中断
        if (e.kind == ApiErrorKind.httpUnauthorized) {
          _poll?.cancel();
          _phase = AnalysisPhase.failed;
          _error = e.message;
          notifyListeners();
          onFailed(_error!);
        }
      } catch (_) {
        // 其它异常忽略，等下个 tick
      }
    }

    tick();
    _poll = Timer.periodic(const Duration(seconds: 3), (_) => tick());
  }

  Future<AnalysisReport> loadReport(String analysisId) =>
      _repo.getReport(analysisId);

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }
}
