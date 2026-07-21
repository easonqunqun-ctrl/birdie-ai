import '../../core/api_client.dart';
import '../models/training.dart';
import '../models/user.dart';

/// 用户域仓库：对照 client/src/services/userService.ts。
class UserRepository {
  UserRepository(this._api);
  final ApiClient _api;

  static const _authTimeout = Duration(seconds: 60);

  Future<WechatLoginResult> wechatLogin({
    required String code,
    String? inviteCode,
  }) async {
    // App 端走 open-login（对齐小程序 rn 分支）
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/wechat-open-login',
      data: {
        'code': code,
        if (inviteCode != null && inviteCode.isNotEmpty) 'invite_code': inviteCode,
      },
      noAuth: true,
      timeout: _authTimeout,
    );
    return WechatLoginResult.fromJson(data);
  }

  Future<User> getMe() async {
    final data =
        await _api.get<Map<String, dynamic>>('/users/me', timeout: _authTimeout);
    return User.fromJson(data);
  }

  Future<User> completeOnboarding({
    required String golfLevel,
    required List<String> primaryGoals,
    required String weeklyPracticeFrequency,
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/users/me/onboarding',
      data: {
        'golf_level': golfLevel,
        'primary_goals': primaryGoals,
        'weekly_practice_frequency': weeklyPracticeFrequency,
      },
    );
    return User.fromJson(data);
  }

  Future<User> updateMe(Map<String, dynamic> payload) async {
    final data = await _api.patch<Map<String, dynamic>>('/users/me', data: payload);
    return User.fromJson(data);
  }

  Future<User> requestAccountDeletion(String confirmText) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/users/me/account-deletion',
      data: {'confirm_text': confirmText},
    );
    return User.fromJson(data);
  }

  Future<User> cancelAccountDeletion() async {
    final data = await _api
        .post<Map<String, dynamic>>('/users/me/account-deletion/cancel', data: {});
    return User.fromJson(data);
  }

  // ---- 装备清单（/users/me/clubs）----
  Future<List<UserClub>> listClubs() async {
    final data = await _api.get<Map<String, dynamic>>('/users/me/clubs');
    return (data['items'] as List?)
            ?.map((e) => UserClub.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [];
  }

  Future<void> deleteClub(String clubId) => _api.del('/users/me/clubs/$clubId');
}
