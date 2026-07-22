import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/apple_auth.dart';
import '../../core/env.dart';
import '../../core/storage.dart';
import '../../core/wechat_auth.dart';
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
    // API 环境切换（如 localhost → 线上）时清掉旧会话，避免带着失效 token 卡在引导页
    final base = Env.apiBase;
    if (s.lastApiBase.isNotEmpty && s.lastApiBase != base) {
      await s.clearAuthSession();
    }
    await s.setLastApiBase(base);

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
      if (e.kind == ApiErrorKind.httpUnauthorized ||
          e.kind == ApiErrorKind.network) {
        await s.clearAuthSession();
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
  /// 用稳定 code 换取**真 JWT**；否则拉起 fluwx OAuth。
  Future<({bool isNewUser, User user})> loginWithWechat(
      {String? inviteCode}) async {
    _loading = true;
    notifyListeners();
    try {
      if (Env.mockLogin) {
        return await _applyLoginResult(
            await _repo.wechatLogin(
                code: await _stableMockCode(), inviteCode: inviteCode));
      }
      final code = await WechatAuth.requestAuthCode();
      return await _applyLoginResult(
          await _repo.wechatLogin(code: code, inviteCode: inviteCode));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Sign in with Apple（iOS）。
  Future<({bool isNewUser, User user})> loginWithApple(
      {String? inviteCode}) async {
    _loading = true;
    notifyListeners();
    try {
      final cred = await AppleAuth.requestCredential();
      return await _applyLoginResult(await _repo.appleLogin(
        identityToken: cred.identityToken,
        fullName: cred.fullName,
        inviteCode: inviteCode,
      ));
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<String> _stableMockCode() async {
    final s = AppStorage.instance;
    var code = s.mockCode;
    if (code.isEmpty) {
      code = 'mock-app-${DateTime.now().millisecondsSinceEpoch}';
      await s.setMockCode(code);
    }
    return code;
  }

  Future<({bool isNewUser, User user})> _applyLoginResult(
      WechatLoginResult res) async {
    _token = res.token;
    _user = res.user;
    _currentRole = 'user';
    final s = AppStorage.instance;
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
