import 'dart:async';
import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/sanitize_swing_candidates.dart';
import '../../data/models/analysis.dart';
import '../../data/repositories/analysis_repository.dart';

enum AnalysisPhase { idle, uploading, creating, processing, completed, failed }

/// 挥杆分析编排：对照 client/src/store/analysisStore.ts。
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
  PendingSwingSelection? _pendingSwing;

  AnalysisPhase get phase => _phase;
  double get uploadProgress => _uploadProgress;
  int get stageProgress => _stageProgress;
  String? get stage => _stage;
  int? get remainingSeconds => _remainingSeconds;
  String? get analysisId => _analysisId;
  String? get error => _error;
  PendingSwingSelection? get pendingSwing => _pendingSwing;
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
    _pendingSwing = null;
    notifyListeners();
  }

  void clearPendingSwing() {
    _pendingSwing = null;
    notifyListeners();
  }

  /// 上传视频，返回 uploadId。不创建分析任务。
  Future<UploadToken> uploadOnly({
    required String filePath,
    required int fileSize,
    required double duration,
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
      _phase = AnalysisPhase.idle;
      notifyListeners();
      return token;
    } catch (e) {
      _phase = AnalysisPhase.failed;
      _error = describeRequestFailure(e).fatalMessage;
      notifyListeners();
      rethrow;
    }
  }

  /// 尝试 detect-swings；超时/失败返回 null（调用方直创任务）。
  Future<DetectSwingsResult?> tryDetectSwings(String uploadId,
      {Duration timeout = const Duration(milliseconds: 1500)}) async {
    try {
      return await _repo.detectSwings(uploadId).timeout(timeout);
    } catch (_) {
      return null;
    }
  }

  /// 多段时写入 pending；返回是否应进入选段页。
  bool stagePendingIfMulti({
    required UploadToken token,
    required DetectSwingsResult detected,
    required String cameraAngle,
    required String clubType,
    required String mode,
    required double duration,
    required int size,
    int? targetYardage,
  }) {
    final sanitized = sanitizeSwingCandidates(
      detected.swingCandidates,
      detected.defaultSelectedIndex,
    );
    if (sanitized.candidates.length <= 1) return false;
    _pendingSwing = PendingSwingSelection(
      uploadId: token.uploadId,
      cameraAngle: cameraAngle,
      clubType: clubType,
      mode: mode,
      targetYardage: targetYardage,
      duration: duration,
      size: size,
      swingCandidates: sanitized.candidates,
      defaultSelectedIndex: sanitized.defaultIndex,
    );
    notifyListeners();
    return true;
  }

  /// 创建分析任务，返回 analysisId。
  Future<String> createAnalysisTask({
    required String uploadId,
    required String cameraAngle,
    required String clubType,
    String mode = 'full_swing',
    int? targetYardage,
    int? selectedSwingIndex,
  }) async {
    _error = null;
    _phase = AnalysisPhase.creating;
    notifyListeners();
    try {
      final created = await _repo.createAnalysis(
        uploadId: uploadId,
        cameraAngle: cameraAngle,
        clubType: clubType,
        mode: mode,
        targetYardage: targetYardage,
        selectedSwingIndex: selectedSwingIndex,
      );
      _analysisId = created.analysisId;
      _remainingSeconds = created.estimatedSeconds;
      _pendingSwing = null;
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

  /// 兼容旧入口：上传 → 创建（无选段）。
  Future<String> startAnalysis({
    required String filePath,
    required int fileSize,
    required double duration,
    required String cameraAngle,
    required String clubType,
    String mode = 'full_swing',
  }) async {
    final token = await uploadOnly(
      filePath: filePath,
      fileSize: fileSize,
      duration: duration,
    );
    return createAnalysisTask(
      uploadId: token.uploadId,
      cameraAngle: cameraAngle,
      clubType: clubType,
      mode: mode,
    );
  }

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
        if (e.kind == ApiErrorKind.httpUnauthorized) {
          _poll?.cancel();
          _phase = AnalysisPhase.failed;
          _error = e.message;
          notifyListeners();
          onFailed(_error!);
        }
      } catch (_) {}
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
