// 挥杆分析 DTO：对照 client/src/types/analysis.ts，与 backend schemas/analysis.py 对齐。

class UploadToken {
  final String uploadId;
  final String uploadUrl;
  final String key;
  final Map<String, String> fields;
  final String? expiresAt;

  const UploadToken({
    required this.uploadId,
    required this.uploadUrl,
    required this.key,
    required this.fields,
    this.expiresAt,
  });

  factory UploadToken.fromJson(Map<String, dynamic> j) => UploadToken(
        uploadId: j['upload_id']?.toString() ?? '',
        uploadUrl: j['upload_url']?.toString() ?? '',
        key: j['key']?.toString() ?? '',
        fields: (j['fields'] as Map?)?.map(
              (k, v) => MapEntry(k.toString(), v.toString()),
            ) ??
            const {},
        expiresAt: j['expires_at'] as String?,
      );
}

class CreateAnalysisResult {
  final String analysisId;
  final String status;
  final int queuePosition;
  final int estimatedSeconds;

  const CreateAnalysisResult({
    required this.analysisId,
    required this.status,
    required this.queuePosition,
    required this.estimatedSeconds,
  });

  factory CreateAnalysisResult.fromJson(Map<String, dynamic> j) =>
      CreateAnalysisResult(
        analysisId: j['analysis_id']?.toString() ?? '',
        status: j['status']?.toString() ?? 'pending',
        queuePosition: (j['queue_position'] as num?)?.toInt() ?? 0,
        estimatedSeconds: (j['estimated_seconds'] as num?)?.toInt() ?? 25,
      );
}

class AnalysisErrorInfo {
  final int code;
  final String message;
  final bool quotaRefunded;
  const AnalysisErrorInfo(
      {required this.code, required this.message, this.quotaRefunded = false});

  factory AnalysisErrorInfo.fromJson(Map<String, dynamic> j) => AnalysisErrorInfo(
        code: (j['code'] as num?)?.toInt() ?? 0,
        message: j['message']?.toString() ?? '',
        quotaRefunded: j['quota_refunded'] == true,
      );
}

class AnalysisStatusInfo {
  final String analysisId;
  final String status; // pending/processing/completed/failed
  final String? stage;
  final int stageProgress;
  final int? estimatedRemainingSeconds;
  final AnalysisErrorInfo? error;

  const AnalysisStatusInfo({
    required this.analysisId,
    required this.status,
    this.stage,
    this.stageProgress = 0,
    this.estimatedRemainingSeconds,
    this.error,
  });

  bool get isCompleted => status == 'completed';
  bool get isFailed => status == 'failed';

  factory AnalysisStatusInfo.fromJson(Map<String, dynamic> j) =>
      AnalysisStatusInfo(
        analysisId: j['analysis_id']?.toString() ?? '',
        status: j['status']?.toString() ?? 'pending',
        stage: j['stage'] as String?,
        stageProgress: (j['stage_progress'] as num?)?.toInt() ?? 0,
        estimatedRemainingSeconds:
            (j['estimated_remaining_seconds'] as num?)?.toInt(),
        error: j['error'] is Map<String, dynamic>
            ? AnalysisErrorInfo.fromJson(j['error'] as Map<String, dynamic>)
            : null,
      );
}

class PhaseScore {
  final num score;
  final String label;
  final bool isWeakest;
  const PhaseScore(
      {required this.score, required this.label, this.isWeakest = false});

  factory PhaseScore.fromJson(Map<String, dynamic> j) => PhaseScore(
        score: (j['score'] as num?) ?? 0,
        label: j['label']?.toString() ?? '',
        isWeakest: j['is_weakest'] == true,
      );
}

class PhaseWindow {
  final double start;
  final double end;
  const PhaseWindow({required this.start, required this.end});

  factory PhaseWindow.fromJson(Map<String, dynamic> j) => PhaseWindow(
        start: (j['start'] as num?)?.toDouble() ?? 0,
        end: (j['end'] as num?)?.toDouble() ?? 0,
      );
}

class AnalysisIssue {
  final String type;
  final String name;
  final String severity; // high/medium/low
  final String description;
  final String? keyFrameUrl;
  final double? keyFrameTimestamp;
  final String? confidenceTier; // confirmed/leaning/hidden

  const AnalysisIssue({
    required this.type,
    required this.name,
    required this.severity,
    required this.description,
    this.keyFrameUrl,
    this.keyFrameTimestamp,
    this.confidenceTier,
  });

  factory AnalysisIssue.fromJson(Map<String, dynamic> j) => AnalysisIssue(
        type: j['type']?.toString() ?? '',
        name: j['name']?.toString() ?? '',
        severity: j['severity']?.toString() ?? 'medium',
        description: j['description']?.toString() ?? '',
        keyFrameUrl: j['key_frame_url'] as String?,
        keyFrameTimestamp: (j['key_frame_timestamp'] as num?)?.toDouble(),
        confidenceTier: j['confidence_tier'] as String?,
      );
}

class AnalysisRecommendation {
  final String drillId;
  final String? targetIssue;
  final int sortOrder;
  const AnalysisRecommendation(
      {required this.drillId, this.targetIssue, this.sortOrder = 0});

  factory AnalysisRecommendation.fromJson(Map<String, dynamic> j) =>
      AnalysisRecommendation(
        drillId: j['drill_id']?.toString() ?? '',
        targetIssue: j['target_issue'] as String?,
        sortOrder: (j['sort_order'] as num?)?.toInt() ?? 0,
      );
}

class AnalysisReport {
  final String id;
  final String status;
  final String cameraAngle;
  final String clubType;
  final String? analysisMode;
  final String videoUrl;
  final double? videoDuration;
  final String? skeletonVideoUrl;
  final String? thumbnailUrl;
  final num? overallScore;
  final String? scoreLevel;
  final num? scoreChange;
  final Map<String, PhaseScore> phaseScores;
  final Map<String, PhaseWindow> phaseTimestamps;
  final List<AnalysisIssue> issues;
  final List<AnalysisRecommendation> recommendations;
  final List<String> qualityWarnings;
  final num? analysisConfidence;
  final List<String> phaseHighlights;
  final String? createdAt;
  final String? analyzedAt;

  const AnalysisReport({
    required this.id,
    required this.status,
    required this.cameraAngle,
    required this.clubType,
    this.analysisMode,
    required this.videoUrl,
    this.videoDuration,
    this.skeletonVideoUrl,
    this.thumbnailUrl,
    this.overallScore,
    this.scoreLevel,
    this.scoreChange,
    this.phaseScores = const {},
    this.phaseTimestamps = const {},
    this.issues = const [],
    this.recommendations = const [],
    this.qualityWarnings = const [],
    this.analysisConfidence,
    this.phaseHighlights = const [],
    this.createdAt,
    this.analyzedAt,
  });

  factory AnalysisReport.fromJson(Map<String, dynamic> j) => AnalysisReport(
        id: j['id']?.toString() ?? '',
        status: j['status']?.toString() ?? 'completed',
        cameraAngle: j['camera_angle']?.toString() ?? 'face_on',
        clubType: j['club_type']?.toString() ?? 'unknown',
        analysisMode: j['analysis_mode'] as String?,
        videoUrl: j['video_url']?.toString() ?? '',
        videoDuration: (j['video_duration'] as num?)?.toDouble(),
        skeletonVideoUrl: j['skeleton_video_url'] as String?,
        thumbnailUrl: j['thumbnail_url'] as String?,
        overallScore: j['overall_score'] as num?,
        scoreLevel: j['score_level'] as String?,
        scoreChange: j['score_change'] as num?,
        phaseScores: (j['phase_scores'] as Map?)?.map(
              (k, v) => MapEntry(
                  k.toString(), PhaseScore.fromJson(v as Map<String, dynamic>)),
            ) ??
            const {},
        phaseTimestamps: (j['phase_timestamps'] as Map?)?.map(
              (k, v) => MapEntry(k.toString(),
                  PhaseWindow.fromJson((v as Map).cast<String, dynamic>())),
            ) ??
            const {},
        issues: (j['issues'] as List?)
                ?.map((e) => AnalysisIssue.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        recommendations: (j['recommendations'] as List?)
                ?.map((e) =>
                    AnalysisRecommendation.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        qualityWarnings: (j['quality_warnings'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            const [],
        analysisConfidence: j['analysis_confidence'] as num?,
        phaseHighlights: (j['phase_highlights'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            const [],
        createdAt: j['created_at'] as String?,
        analyzedAt: j['analyzed_at'] as String?,
      );
}

class AnalysisListPage {
  final List<AnalysisListItem> items;
  final int total;
  final int page;
  final int pageSize;
  const AnalysisListPage({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });
}

class AnalysisListItem {
  final String id;
  final String status;
  final String clubType;
  final String cameraAngle;
  final String? thumbnailUrl;
  final num? overallScore;
  final String? scoreLevel;
  final num? scoreChange;
  final String? analyzedAt;
  final String? createdAt;

  const AnalysisListItem({
    required this.id,
    required this.status,
    required this.clubType,
    required this.cameraAngle,
    this.thumbnailUrl,
    this.overallScore,
    this.scoreLevel,
    this.scoreChange,
    this.analyzedAt,
    this.createdAt,
  });

  factory AnalysisListItem.fromJson(Map<String, dynamic> j) => AnalysisListItem(
        id: j['id']?.toString() ?? '',
        status: j['status']?.toString() ?? 'completed',
        clubType: j['club_type']?.toString() ?? 'unknown',
        cameraAngle: j['camera_angle']?.toString() ?? 'face_on',
        thumbnailUrl: j['thumbnail_url'] as String?,
        overallScore: j['overall_score'] as num?,
        scoreLevel: j['score_level'] as String?,
        scoreChange: j['score_change'] as num?,
        analyzedAt: j['analyzed_at'] as String?,
        createdAt: j['created_at'] as String?,
      );
}
