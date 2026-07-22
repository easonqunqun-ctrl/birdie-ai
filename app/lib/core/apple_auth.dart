import 'dart:io';

import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import 'api_client.dart';
import 'env.dart';

/// Sign in with Apple 封装。
class AppleAuth {
  AppleAuth._();

  static Future<bool> get isAvailable async {
    if (!Platform.isIOS && !Platform.isMacOS) return false;
    return SignInWithApple.isAvailable();
  }

  /// 返回 identityToken + 可选全名。
  static Future<({String identityToken, String? fullName})> requestCredential() async {
    if (Env.mockLogin && Env.appleMockToken.isNotEmpty) {
      return (identityToken: Env.appleMockToken, fullName: 'Apple球友');
    }
    try {
      final cred = await SignInWithApple.getAppleIDCredential(
        scopes: [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );
      final token = cred.identityToken;
      if (token == null || token.isEmpty) {
        throw ApiException(ApiErrorKind.business, 'Apple 未返回登录凭证');
      }
      final parts = <String>[
        if (cred.givenName?.isNotEmpty == true) cred.givenName!,
        if (cred.familyName?.isNotEmpty == true) cred.familyName!,
      ];
      final name = parts.isEmpty ? null : parts.join(' ');
      return (identityToken: token, fullName: name);
    } on SignInWithAppleAuthorizationException catch (e) {
      if (e.code == AuthorizationErrorCode.canceled) {
        throw ApiException(ApiErrorKind.business, '已取消 Apple 登录');
      }
      throw ApiException(ApiErrorKind.business, 'Apple 登录失败：${e.message}');
    }
  }
}
