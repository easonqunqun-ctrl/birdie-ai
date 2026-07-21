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
