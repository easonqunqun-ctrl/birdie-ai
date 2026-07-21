// 用户相关 DTO：对照 client/src/types/api.ts 的 User / UserQuota / UserStats。
// golf_level / membership_type 等枚举先用 String（与后端字符串一致），避免过度设计。

class UserStats {
  final int totalAnalyses;
  final int totalPractices;
  final int streakDays;
  final num bestScore;
  final num scoreImprovement;

  const UserStats({
    required this.totalAnalyses,
    required this.totalPractices,
    required this.streakDays,
    required this.bestScore,
    required this.scoreImprovement,
  });

  factory UserStats.fromJson(Map<String, dynamic> j) => UserStats(
        totalAnalyses: (j['total_analyses'] as num?)?.toInt() ?? 0,
        totalPractices: (j['total_practices'] as num?)?.toInt() ?? 0,
        streakDays: (j['streak_days'] as num?)?.toInt() ?? 0,
        bestScore: (j['best_score'] as num?) ?? 0,
        scoreImprovement: (j['score_improvement'] as num?) ?? 0,
      );
}

class UserQuota {
  final int analysisRemaining;
  final int analysisTotal;
  final String? analysisResetAt;
  final int chatRemainingToday;
  final int chatTotalToday;

  const UserQuota({
    required this.analysisRemaining,
    required this.analysisTotal,
    required this.analysisResetAt,
    required this.chatRemainingToday,
    required this.chatTotalToday,
  });

  factory UserQuota.fromJson(Map<String, dynamic> j) => UserQuota(
        analysisRemaining: (j['analysis_remaining'] as num?)?.toInt() ?? 0,
        analysisTotal: (j['analysis_total'] as num?)?.toInt() ?? 0,
        analysisResetAt: j['analysis_reset_at'] as String?,
        chatRemainingToday: (j['chat_remaining_today'] as num?)?.toInt() ?? 0,
        chatTotalToday: (j['chat_total_today'] as num?)?.toInt() ?? 0,
      );
}

class User {
  final String id;
  final String? nickname;
  final String? avatarUrl;
  final String? golfLevel;
  final List<String> primaryGoals;
  final String? weeklyPracticeFrequency;
  final String membershipType;
  final String? membershipExpiresAt;
  final bool isMember;
  final int membershipDaysRemaining;
  final bool onboardingCompleted;
  final bool hasCompletedRealAnalysis;
  final UserStats? stats;
  final UserQuota? quota;
  final String? createdAt;
  final String? accountDeletionScheduledAt;
  final bool isActiveCoach;

  const User({
    required this.id,
    this.nickname,
    this.avatarUrl,
    this.golfLevel,
    this.primaryGoals = const [],
    this.weeklyPracticeFrequency,
    this.membershipType = 'free',
    this.membershipExpiresAt,
    this.isMember = false,
    this.membershipDaysRemaining = 0,
    this.onboardingCompleted = false,
    this.hasCompletedRealAnalysis = false,
    this.stats,
    this.quota,
    this.createdAt,
    this.accountDeletionScheduledAt,
    this.isActiveCoach = false,
  });

  factory User.fromJson(Map<String, dynamic> j) => User(
        id: j['id']?.toString() ?? '',
        nickname: j['nickname'] as String?,
        avatarUrl: j['avatar_url'] as String?,
        golfLevel: j['golf_level'] as String?,
        primaryGoals:
            (j['primary_goals'] as List?)?.map((e) => e.toString()).toList() ??
                const [],
        weeklyPracticeFrequency: j['weekly_practice_frequency'] as String?,
        membershipType: j['membership_type']?.toString() ?? 'free',
        membershipExpiresAt: j['membership_expires_at'] as String?,
        isMember: j['is_member'] == true,
        membershipDaysRemaining:
            (j['membership_days_remaining'] as num?)?.toInt() ?? 0,
        onboardingCompleted: j['onboarding_completed'] == true,
        hasCompletedRealAnalysis: j['has_completed_real_analysis'] == true,
        stats: j['stats'] is Map<String, dynamic>
            ? UserStats.fromJson(j['stats'] as Map<String, dynamic>)
            : null,
        quota: j['quota'] is Map<String, dynamic>
            ? UserQuota.fromJson(j['quota'] as Map<String, dynamic>)
            : null,
        createdAt: j['created_at'] as String?,
        accountDeletionScheduledAt:
            j['account_deletion_scheduled_at'] as String?,
        isActiveCoach: j['is_active_coach'] == true,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'nickname': nickname,
        'avatar_url': avatarUrl,
        'golf_level': golfLevel,
        'primary_goals': primaryGoals,
        'weekly_practice_frequency': weeklyPracticeFrequency,
        'membership_type': membershipType,
        'membership_expires_at': membershipExpiresAt,
        'is_member': isMember,
        'membership_days_remaining': membershipDaysRemaining,
        'onboarding_completed': onboardingCompleted,
        'has_completed_real_analysis': hasCompletedRealAnalysis,
        'stats': stats == null
            ? null
            : {
                'total_analyses': stats!.totalAnalyses,
                'total_practices': stats!.totalPractices,
                'streak_days': stats!.streakDays,
                'best_score': stats!.bestScore,
                'score_improvement': stats!.scoreImprovement,
              },
        'quota': quota == null
            ? null
            : {
                'analysis_remaining': quota!.analysisRemaining,
                'analysis_total': quota!.analysisTotal,
                'analysis_reset_at': quota!.analysisResetAt,
                'chat_remaining_today': quota!.chatRemainingToday,
                'chat_total_today': quota!.chatTotalToday,
              },
        'created_at': createdAt,
        'account_deletion_scheduled_at': accountDeletionScheduledAt,
        'is_active_coach': isActiveCoach,
      };

  User copyWith({bool? onboardingCompleted}) => User(
        id: id,
        nickname: nickname,
        avatarUrl: avatarUrl,
        golfLevel: golfLevel,
        primaryGoals: primaryGoals,
        weeklyPracticeFrequency: weeklyPracticeFrequency,
        membershipType: membershipType,
        membershipExpiresAt: membershipExpiresAt,
        isMember: isMember,
        membershipDaysRemaining: membershipDaysRemaining,
        onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
        hasCompletedRealAnalysis: hasCompletedRealAnalysis,
        stats: stats,
        quota: quota,
        createdAt: createdAt,
        accountDeletionScheduledAt: accountDeletionScheduledAt,
        isActiveCoach: isActiveCoach,
      );
}

class WechatLoginResult {
  final String token;
  final int expiresIn;
  final bool isNewUser;
  final User user;

  const WechatLoginResult({
    required this.token,
    required this.expiresIn,
    required this.isNewUser,
    required this.user,
  });

  factory WechatLoginResult.fromJson(Map<String, dynamic> j) =>
      WechatLoginResult(
        token: j['token']?.toString() ?? '',
        expiresIn: (j['expires_in'] as num?)?.toInt() ?? 0,
        isNewUser: j['is_new_user'] == true,
        user: User.fromJson(j['user'] as Map<String, dynamic>),
      );
}
