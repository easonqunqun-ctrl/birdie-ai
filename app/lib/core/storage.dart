import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 本地存储：对照 client/src/utils/storage.ts。
/// - token：安全存储（keychain / keystore）
/// - user / role / agreed_terms / 引导标记：SharedPreferences
///
/// 用法：`await AppStorage.instance.init()`（main 里调一次），之后同步读、异步写。
class AppStorage {
  AppStorage._();
  static final AppStorage instance = AppStorage._();

  static const _tokenKey = 'auth_token';
  static const _userKey = 'auth_user';
  static const _roleKey = 'auth_role';
  static const _agreedTermsKey = 'agreed_terms';
  static const _analysisGuideSeenKey = 'analysis_guide_seen';
  static const _mockCodeKey = 'mock_login_code';

  /// 协议版本，对齐 storage.ts CURRENT_TERMS_VERSION，修订须 bump。
  static const currentTermsVersion = 'v1.3';

  final _secure = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  late SharedPreferences _prefs;
  String _token = '';

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _token = (await _secure.read(key: _tokenKey)) ?? '';
  }

  // ---- token（同步读，写异步落盘）----
  String get token => _token;

  Future<void> setToken(String value) async {
    _token = value;
    await _secure.write(key: _tokenKey, value: value);
  }

  Future<void> clearToken() async {
    _token = '';
    await _secure.delete(key: _tokenKey);
  }

  // ---- role ----
  String get role {
    final r = _prefs.getString(_roleKey);
    return r == 'coach' ? 'coach' : 'user';
  }

  Future<void> setRole(String role) => _prefs.setString(_roleKey, role);

  // ---- user ----
  Map<String, dynamic>? get user {
    final raw = _prefs.getString(_userKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      final v = jsonDecode(raw);
      return v is Map<String, dynamic> ? v : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> setUser(Map<String, dynamic> user) =>
      _prefs.setString(_userKey, jsonEncode(user));

  Future<void> clearUser() => _prefs.remove(_userKey);

  // ---- 协议同意 ----
  bool hasAgreedCurrentTerms() {
    final raw = _prefs.getString(_agreedTermsKey);
    if (raw == null) return false;
    try {
      final rec = jsonDecode(raw) as Map<String, dynamic>;
      return rec['version'] == currentTermsVersion;
    } catch (_) {
      return false;
    }
  }

  Future<void> setAgreedTerms(String version) => _prefs.setString(
        _agreedTermsKey,
        jsonEncode({'version': version, 'agreedAt': DateTime.now().millisecondsSinceEpoch}),
      );

  // ---- mock 登录稳定 code（保证每次映射到同一虚拟用户）----
  String get mockCode => _prefs.getString(_mockCodeKey) ?? '';
  Future<void> setMockCode(String code) =>
      _prefs.setString(_mockCodeKey, code);

  // ---- 拍摄引导 ----
  bool get hasSeenAnalysisGuide => _prefs.getBool(_analysisGuideSeenKey) ?? false;
  Future<void> markAnalysisGuideSeen() =>
      _prefs.setBool(_analysisGuideSeenKey, true);
  Future<void> clearAnalysisGuideSeen() =>
      _prefs.remove(_analysisGuideSeenKey);

  /// 退出登录 / 注销：只清账号身份，保留设备级数据（协议同意、引导）。
  Future<void> clearAuthSession() async {
    await clearToken();
    await _prefs.remove(_userKey);
    await _prefs.remove(_roleKey);
  }
}
