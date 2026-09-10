import 'package:flutter/material.dart';

import 'storage.dart';

/// I18N-00：跟随系统，或强制简体 / 英语。
class LocaleController extends ChangeNotifier {
  LocaleController(this._storage) : _preference = _storage.localePreference;

  final AppStorage _storage;
  String _preference;

  /// 空、`zh`、`en`
  String get preference => _preference;

  Locale? get localeOverride => switch (_preference) {
        'en' => const Locale('en'),
        'zh' => const Locale('zh'),
        _ => null,
      };

  String get acceptLanguage {
    final stored = _storage.acceptLanguageHeader();
    if (stored.isNotEmpty) return stored;
    final code =
        WidgetsBinding.instance.platformDispatcher.locale.languageCode;
    return code == 'en' ? 'en-US' : 'zh-CN';
  }

  Future<void> setPreference(String code) async {
    _preference = code;
    await _storage.setLocalePreference(code);
    notifyListeners();
  }
}
