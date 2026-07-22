import 'package:flutter/foundation.dart';

/// 多环境配置。对齐 client/.env.*：生产 API_BASE = https://api.birdieai.cn/v1。
///
/// 真机 Debug 勿用 localhost（指向手机自身）。示例：
///   flutter run --dart-define=API_BASE=http://192.168.2.196:8000/v1
///   flutter run --dart-define=APP_ENV=staging   # → https://api.birdieai.cn/v1 + 客户端 mock
///   flutter run --dart-define=APP_ENV=production
///   flutter run --dart-define=WECHAT_OPEN_APPID=wx… --dart-define=WECHAT_UNIVERSAL_LINK=https://api.birdieai.cn/app/
class Env {
  Env._();

  static const String _appEnvDefine =
      String.fromEnvironment('APP_ENV', defaultValue: '');

  static const String _apiBaseOverride =
      String.fromEnvironment('API_BASE', defaultValue: '');

  /// 是否走客户端 mock 登录。
  /// 生产强制关闭；其余环境默认开启，可用 --dart-define=MOCK_LOGIN=false 覆盖。
  static const bool _mockLoginOverride =
      bool.fromEnvironment('MOCK_LOGIN', defaultValue: true);

  static const String wechatOpenAppId =
      String.fromEnvironment('WECHAT_OPEN_APPID', defaultValue: '');

  static const String wechatUniversalLink = String.fromEnvironment(
    'WECHAT_UNIVERSAL_LINK',
    defaultValue: 'https://api.birdieai.cn/app/',
  );

  /// 仅联调：非空且 mockLogin 时，Apple 登录直接用该 mock token。
  static const String appleMockToken =
      String.fromEnvironment('APPLE_MOCK_TOKEN', defaultValue: '');

  static String get appEnv {
    if (_appEnvDefine.isNotEmpty) return _appEnvDefine;
    // Release 未指定时默认生产，避免真机装包仍打 localhost
    return kReleaseMode ? 'production' : 'development';
  }

  static bool get isProduction => appEnv == 'production';

  static String get apiBase {
    if (_apiBaseOverride.isNotEmpty) return _apiBaseOverride;
    switch (appEnv) {
      case 'production':
      case 'staging':
      case 'test':
        return 'https://api.birdieai.cn/v1';
      default:
        // 仅模拟器可靠；真机请用 --dart-define=API_BASE=http://<Mac局域网IP>:8000/v1
        return 'http://127.0.0.1:8000/v1';
    }
  }

  static bool get mockLogin => !isProduction && _mockLoginOverride;

  /// 公开报告 / 分享落地页（H5 或后续 Universal Link）。
  static String publicReportUrl(String analysisId) =>
      'https://api.birdieai.cn/v1/analyses/$analysisId/public';

  /// 非 prod 显示环境角标（等价小程序 EnvBadge）
  static bool get showEnvBadge => !isProduction;
  static String get envLabel => appEnv;
}
