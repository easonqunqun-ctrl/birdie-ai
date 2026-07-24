// 长尾内容 DTO：对照 coursesService / prosService / meetupEventService。

class Course {
  final String id;
  final String title;
  final String? subtitle;
  final String? coverUrl;
  final int stage;
  final bool isMemberOnly;
  final int estimatedMinutes;

  const Course({
    required this.id,
    required this.title,
    this.subtitle,
    this.coverUrl,
    this.stage = 1,
    this.isMemberOnly = false,
    this.estimatedMinutes = 0,
  });

  factory Course.fromJson(Map<String, dynamic> j) => Course(
        id: j['id']?.toString() ?? '',
        title: j['title']?.toString() ?? '',
        subtitle: j['subtitle'] as String?,
        coverUrl: j['cover_url'] as String?,
        stage: (j['stage'] as num?)?.toInt() ?? 1,
        isMemberOnly: j['is_member_only'] == true,
        estimatedMinutes: (j['estimated_minutes'] as num?)?.toInt() ?? 0,
      );
}

class ProPlayer {
  final String id;
  final String name;
  final String? nameEn;
  final String? nationality;
  final String? avatarUrl;
  final String? shortBio;

  const ProPlayer({
    required this.id,
    required this.name,
    this.nameEn,
    this.nationality,
    this.avatarUrl,
    this.shortBio,
  });

  factory ProPlayer.fromJson(Map<String, dynamic> j) => ProPlayer(
        id: j['id']?.toString() ?? '',
        name: j['name']?.toString() ?? '',
        nameEn: j['name_en'] as String?,
        nationality: j['nationality'] as String?,
        avatarUrl: j['avatar_url'] as String?,
        shortBio: j['short_bio'] as String?,
      );
}

/// M12-04 · 职业镜头（pro-matches 内嵌）
class ProSwingClip {
  final String id;
  final String proPlayerId;
  final String clubType;
  final String cameraAngle;
  final String videoUrl;
  final String? thumbnailUrl;
  final num? overallScore;
  final Map<String, dynamic> featuresSnapshot;
  final String sourceCredit;

  const ProSwingClip({
    required this.id,
    required this.proPlayerId,
    required this.clubType,
    required this.cameraAngle,
    required this.videoUrl,
    this.thumbnailUrl,
    this.overallScore,
    this.featuresSnapshot = const {},
    this.sourceCredit = '',
  });

  factory ProSwingClip.fromJson(Map<String, dynamic> j) => ProSwingClip(
        id: j['id']?.toString() ?? '',
        proPlayerId: j['pro_player_id']?.toString() ?? '',
        clubType: j['club_type']?.toString() ?? '',
        cameraAngle: j['camera_angle']?.toString() ?? '',
        videoUrl: j['video_url']?.toString() ?? '',
        thumbnailUrl: j['thumbnail_url'] as String?,
        overallScore: j['overall_score'] as num?,
        featuresSnapshot: (j['features_snapshot'] as Map?)
                ?.map((k, v) => MapEntry(k.toString(), v)) ??
            const {},
        sourceCredit: j['source_credit']?.toString() ?? '',
      );
}

class ProMatchItem {
  final num matchScore;
  final ProSwingClip clip;
  final ProPlayer player;

  const ProMatchItem({
    required this.matchScore,
    required this.clip,
    required this.player,
  });

  factory ProMatchItem.fromJson(Map<String, dynamic> j) => ProMatchItem(
        matchScore: (j['match_score'] as num?) ?? 0,
        clip: ProSwingClip.fromJson(
            (j['clip'] as Map?)?.cast<String, dynamic>() ?? const {}),
        player: ProPlayer.fromJson(
            (j['player'] as Map?)?.cast<String, dynamic>() ?? const {}),
      );
}

class ProMatchResult {
  final String analysisId;
  final List<ProMatchItem> matches;

  const ProMatchResult({required this.analysisId, this.matches = const []});

  factory ProMatchResult.fromJson(Map<String, dynamic> j) => ProMatchResult(
        analysisId: j['analysis_id']?.toString() ?? '',
        matches: (j['matches'] as List?)
                ?.whereType<Map>()
                .map((e) => ProMatchItem.fromJson(e.cast<String, dynamic>()))
                .toList() ??
            const [],
      );
}

class MeetupEvent {
  final String id;
  final String title;
  final String? description;
  final String? templateLabel;
  final String? scheduledAt;
  final int participantCount;
  final int? capacity;
  final String status;

  const MeetupEvent({
    required this.id,
    required this.title,
    this.description,
    this.templateLabel,
    this.scheduledAt,
    this.participantCount = 0,
    this.capacity,
    this.status = '',
  });

  factory MeetupEvent.fromJson(Map<String, dynamic> j) => MeetupEvent(
        id: j['id']?.toString() ?? '',
        title: j['title']?.toString() ?? '',
        description: j['description'] as String?,
        templateLabel: j['template_label'] as String?,
        scheduledAt: j['scheduled_at'] as String?,
        participantCount: (j['participant_count'] as num?)?.toInt() ?? 0,
        capacity: (j['capacity'] as num?)?.toInt(),
        status: j['status']?.toString() ?? '',
      );
}
