import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'env.dart';
import 'storage.dart';

/// 请求异常类别，对照 request.ts RequestError.kind。
enum ApiErrorKind {
  httpUnauthorized,
  httpServerError,
  business,
  badResponse,
  network,
}

/// 统一请求异常。调用方按 [kind] 分流（如 401 清 token、5xx 可重试）。
class ApiException implements Exception {
  final ApiErrorKind kind;
  final String message;
  final int? status;
  final int? code;
  final String? detail;
  final String? requestId;

  ApiException(
    this.kind,
    this.message, {
    this.status,
    this.code,
    this.detail,
    this.requestId,
  });

  @override
  String toString() => 'ApiException($kind, $message, code=$code)';
}

typedef Unauthorized = void Function();

/// 统一请求封装：对照 client/src/services/request.ts。
/// - 自动注入 Bearer Token
/// - 按统一信封 {code,message,data} 解包，code!=0 抛业务异常
/// - 401 清 token 并回调 [onUnauthorized]
class ApiClient {
  ApiClient({this.onUnauthorized});

  final Unauthorized? onUnauthorized;
  final _http = http.Client();
  bool _unauthorizedHandling = false;

  Future<T> get<T>(String path,
          {Map<String, String>? headers, bool noAuth = false, Duration? timeout}) =>
      _request<T>('GET', path,
          headers: headers, noAuth: noAuth, timeout: timeout);

  Future<T> post<T>(String path,
          {Object? data,
          Map<String, String>? headers,
          bool noAuth = false,
          Duration? timeout}) =>
      _request<T>('POST', path,
          data: data, headers: headers, noAuth: noAuth, timeout: timeout);

  Future<T> patch<T>(String path,
          {Object? data, Map<String, String>? headers, Duration? timeout}) =>
      _request<T>('PATCH', path, data: data, headers: headers, timeout: timeout);

  Future<T> put<T>(String path,
          {Object? data, Map<String, String>? headers, Duration? timeout}) =>
      _request<T>('PUT', path, data: data, headers: headers, timeout: timeout);

  Future<T> del<T>(String path,
          {Map<String, String>? headers, Duration? timeout}) =>
      _request<T>('DELETE', path, headers: headers, timeout: timeout);

  Future<T> _request<T>(
    String method,
    String path, {
    Object? data,
    Map<String, String>? headers,
    bool noAuth = false,
    Duration? timeout,
  }) async {
    final base = Env.apiBase;
    if (base.isEmpty) {
      throw ApiException(ApiErrorKind.network, 'API 地址未配置');
    }
    final uri = Uri.parse(path.startsWith('http') ? path : '$base$path');

    final h = <String, String>{
      'Content-Type': 'application/json',
      ...?headers,
    };
    if (!noAuth) {
      final token = AppStorage.instance.token;
      if (token.isNotEmpty) h['Authorization'] = 'Bearer $token';
    }

    http.Response res;
    try {
      final req = http.Request(method, uri)..headers.addAll(h);
      if (data != null) req.body = jsonEncode(data);
      final streamed =
          await _http.send(req).timeout(timeout ?? const Duration(seconds: 15));
      res = await http.Response.fromStream(streamed);
    } on TimeoutException {
      throw ApiException(ApiErrorKind.network, '请求超时，请检查网络与接口是否可达');
    } catch (e) {
      throw ApiException(ApiErrorKind.network, _friendlyNetwork(e.toString()));
    }

    return _handle<T>(res);
  }

  T _handle<T>(http.Response res) {
    final status = res.statusCode;
    Map<String, dynamic>? body;
    try {
      final decoded = jsonDecode(utf8.decode(res.bodyBytes));
      if (decoded is Map<String, dynamic>) body = decoded;
    } catch (_) {}

    final requestId = _requestId(res.headers, body);

    if (status == 401) {
      final bizCode = body?['code'] is int ? body!['code'] as int : null;
      if (bizCode == 40104) {
        final msg = (body?['message'] as String?)?.trim().isNotEmpty == true
            ? (body!['message'] as String).trim()
            : '微信登录凭证已失效，请再点一次登录';
        throw ApiException(ApiErrorKind.business, msg, status: 401, code: bizCode);
      }
      _handleUnauthorized();
      throw ApiException(ApiErrorKind.httpUnauthorized, '未登录或登录已过期',
          status: 401, requestId: requestId);
    }

    if (status == 429) {
      throw ApiException(ApiErrorKind.httpServerError, '请求过于频繁，请稍后再试',
          status: 429, requestId: requestId);
    }

    if (status >= 500) {
      final code = body?['code'];
      if (code is int && code != 0) {
        final msg = (body?['message'] as String?)?.trim();
        throw ApiException(
          ApiErrorKind.business,
          (msg != null && msg.isNotEmpty) ? msg : '服务暂时不可用',
          status: status,
          code: code,
          detail: (body?['detail'] as String?)?.trim(),
          requestId: requestId,
        );
      }
      throw ApiException(ApiErrorKind.httpServerError, 'HTTP $status',
          status: status, requestId: requestId);
    }

    if (body == null || body['code'] is! int) {
      throw ApiException(ApiErrorKind.badResponse, '响应格式错误',
          status: status, requestId: requestId);
    }

    final code = body['code'] as int;
    if (code != 0) {
      final msg = (body['message'] as String?)?.trim();
      throw ApiException(
        ApiErrorKind.business,
        (msg != null && msg.isNotEmpty) ? msg : '业务错误',
        status: status,
        code: code,
        detail: (body['detail'] as String?)?.trim(),
        requestId: requestId,
      );
    }

    return body['data'] as T;
  }

  void _handleUnauthorized() {
    if (_unauthorizedHandling) return;
    _unauthorizedHandling = true;
    AppStorage.instance.clearToken();
    onUnauthorized?.call();
    Timer(const Duration(seconds: 2), () => _unauthorizedHandling = false);
  }

  String? _requestId(Map<String, String> headers, Map<String, dynamic>? body) {
    final fromBody = body?['request_id'];
    if (fromBody is String && fromBody.trim().isNotEmpty) return fromBody.trim();
    final raw = headers['x-request-id'];
    return (raw != null && raw.trim().isNotEmpty) ? raw.trim() : null;
  }

  String _friendlyNetwork(String raw) {
    final r = raw.trim();
    if (r.isEmpty) return '网络异常，请稍后重试';
    final lower = r.toLowerCase();
    if (lower.contains('timeout') || r.contains('超时')) {
      return '请求超时，请检查网络与接口是否可达';
    }
    if (lower.contains('failed host lookup') ||
        lower.contains('getaddrinfo') ||
        lower.contains('nodename')) {
      return '无法解析服务器地址，请检查网络或 API 域名配置';
    }
    if (lower.contains('certificate') || lower.contains('handshake')) {
      return 'HTTPS 证书校验失败：请使用公信 CA 并部署完整证书链';
    }
    if (lower.contains('connection')) {
      return '无法连接服务器，请确认域名解析与防火墙';
    }
    return r.length > 56 ? '${r.substring(0, 55)}…' : r;
  }
}

/// 轮询 / 上传等非 request 通路的用户可见文案，对照 describeIntermittentRequestFailure。
({String fatalMessage, String toastTitle}) describeRequestFailure(Object e) {
  if (e is ApiException) {
    switch (e.kind) {
      case ApiErrorKind.business:
        final t = e.message.trim().isEmpty ? '请求失败' : e.message.trim();
        return (fatalMessage: t, toastTitle: t);
      case ApiErrorKind.httpServerError:
        return (fatalMessage: '服务暂时不可用，已暂停自动刷新', toastTitle: '服务暂时不可用');
      case ApiErrorKind.badResponse:
        return (fatalMessage: '服务器响应异常，已暂停自动刷新', toastTitle: '服务响应异常');
      case ApiErrorKind.httpUnauthorized:
        final t = e.message.trim().isEmpty ? '未登录或登录已过期' : e.message.trim();
        return (fatalMessage: t, toastTitle: t);
      case ApiErrorKind.network:
        final t = e.message.trim();
        if (t.isNotEmpty) return (fatalMessage: t, toastTitle: t);
    }
  }
  return (fatalMessage: '网络似乎不太稳定，已暂停自动刷新', toastTitle: '网络异常，请稍后重试');
}
