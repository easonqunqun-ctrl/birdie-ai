import 'dart:async';

import 'package:fluwx/fluwx.dart';

import 'api_client.dart';
import 'env.dart';

/// 微信开放平台 OAuth：对照 fluwx + POST /auth/wechat-open-login。
class WechatAuth {
  WechatAuth._();
  static final Fluwx _wx = Fluwx();
  static bool _registered = false;

  static Future<void> ensureRegistered() async {
    if (_registered) return;
    final appId = Env.wechatOpenAppId;
    if (appId.isEmpty) {
      throw ApiException(
        ApiErrorKind.business,
        '未配置微信开放平台 AppID（--dart-define=WECHAT_OPEN_APPID=wx…）',
      );
    }
    final ok = await _wx.registerApi(
      appId: appId,
      universalLink: Env.wechatUniversalLink.isEmpty
          ? null
          : Env.wechatUniversalLink,
    );
    if (!ok) {
      throw ApiException(ApiErrorKind.business, '微信 SDK 注册失败，请检查 Universal Link');
    }
    _registered = true;
  }

  /// 拉起微信授权，返回 OAuth `code`。
  static Future<String> requestAuthCode() async {
    await ensureRegistered();
    final installed = await _wx.isWeChatInstalled;
    if (!installed) {
      throw ApiException(ApiErrorKind.business, '请先安装微信客户端');
    }

    final completer = Completer<String>();
    late final FluwxCancelable sub;
    sub = _wx.addSubscriber((response) {
      if (response is! WeChatAuthResponse) return;
      if (completer.isCompleted) return;
      sub.cancel();
      if (response.errCode == 0 && (response.code?.isNotEmpty ?? false)) {
        completer.complete(response.code!);
      } else if (response.errCode == -2) {
        completer.completeError(
            ApiException(ApiErrorKind.business, '已取消微信登录'));
      } else {
        completer.completeError(ApiException(
          ApiErrorKind.business,
          response.errStr?.isNotEmpty == true
              ? response.errStr!
              : '微信授权失败（${response.errCode}）',
        ));
      }
    });

    final started = await _wx.authBy(
      which: NormalAuth(scope: 'snsapi_userinfo', state: 'birdie_login'),
    );
    if (!started) {
      sub.cancel();
      throw ApiException(ApiErrorKind.business, '无法拉起微信授权');
    }

    return completer.future.timeout(
      const Duration(minutes: 2),
      onTimeout: () {
        sub.cancel();
        throw ApiException(ApiErrorKind.business, '微信授权超时');
      },
    );
  }
}
