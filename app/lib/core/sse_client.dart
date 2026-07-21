import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'env.dart';
import 'storage.dart';

typedef SseCancel = void Function();

/// SSE 客户端：对照 client/src/utils/sseClient + chatService.streamMessage。
/// 用 http.Client().send 拿 response.stream，手写 `event:` / `data:` 行解析。
/// 事件序列：message_start → content_delta×N → [attachment×K] → message_end｜error
///
/// 返回 [SseCancel]：页面销毁 / 用户中断时调用可立即断开连接。
SseCancel streamSse({
  required String path,
  required Object body,
  required void Function(String type, Map<String, dynamic> data) onEvent,
  required void Function(Object err, {required bool aborted}) onError,
  void Function()? onDone,
}) {
  final client = http.Client();
  var aborted = false;
  var settled = false;
  StreamSubscription<String>? sub;

  void closeClient() {
    try {
      client.close();
    } catch (_) {}
  }

  Future<void> run() async {
    try {
      final base = Env.apiBase.replaceAll(RegExp(r'/$'), '');
      final uri = Uri.parse(path.startsWith('http') ? path : '$base$path');
      final req = http.Request('POST', uri);
      req.headers['Accept'] = 'text/event-stream';
      req.headers['Content-Type'] = 'application/json';
      final tk = AppStorage.instance.token;
      if (tk.isNotEmpty) req.headers['Authorization'] = 'Bearer $tk';
      req.body = jsonEncode(body);

      final resp =
          await client.send(req).timeout(const Duration(seconds: 60));
      if (resp.statusCode >= 400) {
        settled = true;
        onError(Exception('HTTP ${resp.statusCode}'), aborted: false);
        closeClient();
        return;
      }

      var eventType = 'message';
      final dataLines = <String>[];

      void dispatch() {
        final type = eventType;
        eventType = 'message';
        if (dataLines.isEmpty) return;
        final raw = dataLines.join('\n');
        dataLines.clear();
        if (raw.trim() == '[DONE]') return;
        try {
          final decoded = jsonDecode(raw);
          if (decoded is Map<String, dynamic>) onEvent(type, decoded);
        } catch (_) {
          // 非 JSON（如 ping 文本）忽略
        }
      }

      sub = resp.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen(
        (line) {
          if (line.isEmpty) {
            dispatch();
            return;
          }
          if (line.startsWith(':')) return; // 注释 / keepalive
          if (line.startsWith('event:')) {
            eventType = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            dataLines.add(line.substring(5).replaceFirst(RegExp(r'^ '), ''));
          }
        },
        onDone: () {
          dispatch();
          if (!settled) {
            settled = true;
            onDone?.call();
          }
          closeClient();
        },
        onError: (Object e) {
          if (!settled) {
            settled = true;
            onError(e, aborted: aborted);
          }
          closeClient();
        },
        cancelOnError: true,
      );
    } catch (e) {
      if (!settled) {
        settled = true;
        onError(e, aborted: aborted);
      }
      closeClient();
    }
  }

  run();

  return () {
    aborted = true;
    sub?.cancel();
    closeClient();
  };
}
