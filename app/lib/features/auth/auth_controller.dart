import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/env.dart';
import '../../core/storage.dart';
import '../../data/models/user.dart';
import '../../data/repositories/user_repository.dart';

/// 登录 / 用户态：对照 client/src/store/userStore.ts（Zustand → ChangeNotifier）。
class AuthController extends ChangeNotifier {
  AuthController(this._repo);
  final UserRepository _repo;

  String _token = '';
  User? _user;
  String _currentRole = 'user';
  bool _loading = false;
  bool _initialized = false;

  String get token => _token;
  User? get user => _user;
  String get currentRole => _currentRole;
  bool get loading => _loading;
  bool get initialized => _initialized;
  bool get isLoggedIn => _token.isNotEmpty;

  /// 启动：从缓存恢复 token/user，并尝试拉最新用户信息。
  Future<void> bootstrap() async {
    final s = AppStorage.instance;
    _token = s.token;
    _currentRole = s.role;
    if (_token.isEmpty) {
      _initialized = true;
      notifyListeners();
      return;
    }
    final cached = s.user;
    if (cached != null) {
      _user = User.fromJson(cached);
      _initialized = true;
    }
    _loading = true;
    notifyListeners();

    try {
      final me = await _repo.getMe();
      _user = me;
      await s.setUser(me.toJson());
      _loading = false;
      _initialized = true;
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.httpUnauthorized) {
        await s.clearToken();
        _token = '';
        _user = null;
      }
      _loading = false;
      _initialized = true;
    } catch (_) {
      _loading = false;
      _initialized = true;
    }
    notifyListeners();
  }

  /// 微信一键登录。
  /// Env.mockLogin 时走后端 mock 登录端点（WECHAT_MOCK_LOGIN=true），
  /// 用稳定 code 换取**真 JWT**，从而后续上传/分析/教练都能真跑。
  Future<({bool isNewUser, User user})> loginWithWechat(
      {String? inviteCode}) async {
    _loading = true;
    notifyListeners();
    try {
      if (Env.mockLogin) {
        return await _mockLogin(inviteCode: inviteCode);
      }
      // TODO：接入 fluwx 拿真微信 code 后调 _repo.wechatLogin
      throw ApiException(
          ApiErrorKind.business, '微信登录待接入（当前仅 mock 环境可登录）');
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// 后端 mock 登录：用设备稳定 code 调 /auth/wechat-open-login 拿真 JWT。
  Future<({bool isNewUser, User user})> _mockLogin({String? inviteCode}) async {
    final s = AppStorage.instance;
    var code = s.mockCode;
    if (code.isEmpty) {
      code = 'mock-app-${DateTime.now().millisecondsSinceEpoch}';
      await s.setMockCode(code);
    }
    final res = await _repo.wechatLogin(code: code, inviteCode: inviteCode);
    _token = res.token;
    _user = res.user;
    _currentRole = 'user';
    await s.setToken(_token);
    await s.setUser(res.user.toJson());
    await s.setRole('user');
    return (isNewUser: res.isNewUser, user: res.user);
  }

  /// 完成引导：调后端持久化。
  Future<void> completeOnboarding({
    required String golfLevel,
    required List<String> primaryGoals,
    required String weeklyPracticeFrequency,
  }) async {
    final me = await _repo.completeOnboarding(
      golfLevel: golfLevel,
      primaryGoals: primaryGoals,
      weeklyPracticeFrequency: weeklyPracticeFrequency,
    );
    _user = me;
    await AppStorage.instance.setUser(me.toJson());
    notifyListeners();
  }

  /// 更新档案（昵称 / 水平 / 目标 / 频率）：调后端。
  Future<void> updateProfile(Map<String, dynamic> payload) async {
    final me = await _repo.updateMe(payload);
    _user = me;
    await AppStorage.instance.setUser(me.toJson());
    notifyListeners();
  }

  /// 刷新用户信息（首页/我的等页 onShow 调用）。静默失败不打扰用户。
  Future<void> refresh() async {
    if (_token.isEmpty) return;
    try {
      final me = await _repo.getMe();
      _user = me;
      await AppStorage.instance.setUser(me.toJson());
      notifyListeners();
    } catch (_) {}
  }

  Future<void> logout() async {
    await AppStorage.instance.clearAuthSession();
    _token = '';
    _user = null;
    _currentRole = 'user';
    notifyListeners();
  }

  /// 401 回调：由 ApiClient 触发，清态跳登录。
  void onUnauthorized() {
    _token = '';
    _user = null;
    notifyListeners();
  }
}
