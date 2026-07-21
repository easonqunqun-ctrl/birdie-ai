/// 多环境配置。对齐 client/.env.*：生产 API_BASE = https://api.birdieai.cn/v1。
/// 通过 --dart-define 注入，默认走 dev。
///   flutter run --dart-define=APP_ENV=production
class Env {
  Env._();

  static const String appEnv =
      String.fromEnvironment('APP_ENV', defaultValue: 'development');

  static const String _apiBaseOverride =
      String.fromEnvironment('API_BASE', defaultValue: '');

  /// 是否走客户端 mock 登录（M0：无后端也能跑通闭环）。
  /// 生产强制关闭；其余环境默认开启，可用 --dart-define=MOCK_LOGIN=false 覆盖。
  static const bool _mockLoginOverride =
      bool.fromEnvironment('MOCK_LOGIN', defaultValue: true);

  static bool get isProduction => appEnv == 'production';

  static String get apiBase {
    if (_apiBaseOverride.isNotEmpty) return _apiBaseOverride;
    switch (appEnv) {
      case 'production':
        return 'https://api.birdieai.cn/v1';
      case 'staging':
      case 'test':
        return 'https://api.birdieai.cn/v1';
      default:
        return 'http://localhost:8000/v1';
    }
  }

  static bool get mockLogin => !isProduction && _mockLoginOverride;

  /// 非 prod 显示环境角标（等价小程序 EnvBadge）
  static bool get showEnvBadge => !isProduction;
  static String get envLabel => appEnv;
}
