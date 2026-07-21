import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/sse_client.dart';
import '../../data/models/chat.dart';
import '../../data/repositories/chat_repository.dart';

/// AI 对话状态：对照 client/src/store/chatStore.ts（默认走 SSE 流式）。
/// 不变量：乐观插 user + assistant 占位；delta 追加最后一条 assistant；
/// end 关闭 streaming；error → assistant.errored；传输错误尝试从历史恢复。
class ChatController extends ChangeNotifier {
  ChatController(this._repo);
  final ChatRepository _repo;

  String? _sessionId;
  String? _contextAnalysisId;
  final List<ChatMessage> _messages = [];
  List<QuickQuestion> _quickQuestions = [];
  int _quotaRemaining = -1;
  int _quotaTotal = -1;
  bool _loading = false;
  bool _sending = false;
  String? _bootstrapError;
  SseCancel? _activeStream;

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  List<QuickQuestion> get quickQuestions => _quickQuestions;
  int get quotaRemaining => _quotaRemaining;
  int get quotaTotal => _quotaTotal;
  String? get contextAnalysisId => _contextAnalysisId;
  bool get loading => _loading;
  bool get sending => _sending;
  String? get bootstrapError => _bootstrapError;
  bool get ready => _sessionId != null;

  String _localId(String prefix) =>
      '$prefix-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  Future<void> bootstrapSession({String? contextAnalysisId}) async {
    _loading = true;
    _bootstrapError = null;
    notifyListeners();
    try {
      final results = await Future.wait([
        _repo.getQuickQuestions(),
        _repo.createSession(contextAnalysisId: contextAnalysisId),
      ]);
      _quickQuestions = results[0] as List<QuickQuestion>;
      final session = results[1] as CreateSessionResult;
      _sessionId = session.sessionId;
      _contextAnalysisId = session.contextAnalysisId;
      _messages
        ..clear()
        ..addAll(session.messages);
      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _bootstrapError = describeRequestFailure(e).fatalMessage;
      notifyListeners();
    }
  }

  void hydrateQuota(int remaining, int total) {
    _quotaRemaining = remaining;
    _quotaTotal = total;
    notifyListeners();
  }

  ChatMessage? get _lastAssistant {
    for (var i = _messages.length - 1; i >= 0; i--) {
      if (_messages[i].role == 'assistant') return _messages[i];
    }
    return null;
  }

  /// 流式发送。失败抛 [ChatSubmitException]，页面据 kind 做兜底 UI。
  Future<void> submitMessage(String content) async {
    final text = content.trim();
    if (text.isEmpty) return;
    if (text.length > 500) {
      throw ChatSubmitException(ChatErrorKind.network, '单条消息最多 500 字');
    }
    if (_sessionId == null) {
      throw ChatSubmitException(ChatErrorKind.network, '会话未就绪，请稍后再试');
    }
    if (_sending) return;

    final now = DateTime.now().toIso8601String();
    final userMsg = ChatMessage(
        id: _localId('msg-user'),
        role: 'user',
        content: text,
        attachments: [],
        createdAt: now,
        pending: true);
    final assistantMsg = ChatMessage(
        id: _localId('msg-ai'),
        role: 'assistant',
        content: '',
        attachments: [],
        createdAt: now,
        streaming: true,
        pending: true);
    _messages.addAll([userMsg, assistantMsg]);
    _sending = true;
    notifyListeners();

    final completer = Completer<void>();
    var settled = false;
    var sawAnyEvent = false;

    void finish([ChatSubmitException? err]) {
      if (settled) return;
      settled = true;
      _sending = false;
      _activeStream = null;
      notifyListeners();
      if (err != null) {
        completer.completeError(err);
      } else {
        completer.complete();
      }
    }

    void markErrored(String fallback) {
      final a = _lastAssistant;
      if (a != null) {
        if (a.content.isEmpty) a.content = fallback;
        a.streaming = false;
        a.errored = true;
      }
      notifyListeners();
    }

    Future<bool> recoverFromHistory() async {
      try {
        final items = await _repo.getMessages(_sessionId!, pageSize: 20);
        ChatMessage? lastA;
        for (var i = items.length - 1; i >= 0; i--) {
          if (items[i].role == 'assistant') {
            lastA = items[i];
            break;
          }
        }
        if (lastA == null) return false;
        final a = _lastAssistant;
        if (a != null) {
          a.id = lastA.id;
          a.content = lastA.content;
          a.attachments = lastA.attachments;
          a.streaming = false;
          a.pending = false;
        }
        notifyListeners();
        return true;
      } catch (_) {
        return false;
      }
    }

    _activeStream = _repo.streamMessage(
      _sessionId!,
      text,
      ChatStreamHandlers(
        onStart: (userId, assistantId, userMessage) {
          sawAnyEvent = true;
          userMsg.pending = false;
          if (userMessage['id'] != null) {
            userMsg.id = userMessage['id'].toString();
          }
          assistantMsg.id = assistantId.isNotEmpty ? assistantId : assistantMsg.id;
          assistantMsg.pending = false;
          notifyListeners();
        },
        onDelta: (delta) {
          sawAnyEvent = true;
          final a = _lastAssistant;
          if (a != null) a.content += delta;
          notifyListeners();
        },
        onAttachment: (att) {
          sawAnyEvent = true;
          final a = _lastAssistant;
          if (a != null) a.attachments = [...a.attachments, att];
          notifyListeners();
        },
        onEnd: (assistantId, endContent, attachments, quotaRemaining) {
          sawAnyEvent = true;
          _quotaRemaining = quotaRemaining;
          final a = _lastAssistant;
          if (a != null) {
            if (assistantId.isNotEmpty) a.id = assistantId;
            if (endContent.isNotEmpty) a.content = endContent;
            if (attachments.isNotEmpty) a.attachments = attachments;
            a.streaming = false;
          }
          notifyListeners();
        },
        onBusinessError: (code, message) {
          final kind = switch (code) {
            kErrChatQuotaExhausted => ChatErrorKind.quotaExhausted,
            kErrRateLimit => ChatErrorKind.rateLimit,
            kErrContentViolation => ChatErrorKind.contentViolation,
            _ => ChatErrorKind.serviceError,
          };
          if (kind != ChatErrorKind.contentViolation) {
            markErrored('生成中断，请重试');
          } else {
            // 内容违规未消耗：回滚两条占位
            _messages.remove(userMsg);
            _messages.remove(assistantMsg);
          }
          finish(ChatSubmitException(kind, message));
        },
        onTransportError: (err, {required aborted}) {
          if (aborted) {
            markErrored('已中断');
            finish(ChatSubmitException(ChatErrorKind.network, '已中断'));
            return;
          }
          recoverFromHistory().then((recovered) {
            if (recovered) {
              finish();
            } else {
              markErrored('网络中断');
              finish(ChatSubmitException(
                  ChatErrorKind.network, err.toString()));
            }
          });
        },
        onClose: () {
          if (!sawAnyEvent) {
            recoverFromHistory().then((recovered) {
              if (!recovered) markErrored('生成中断，请重试');
              finish();
            });
            return;
          }
          finish();
        },
      ),
    );

    return completer.future;
  }

  /// 点击气泡重试：回滚最后一轮（user + 失败的 assistant），用同一问题重发。
  Future<void> retryLast() async {
    if (_sending) return;
    var userIdx = -1;
    for (var i = _messages.length - 1; i >= 0; i--) {
      if (_messages[i].role == 'user') {
        userIdx = i;
        break;
      }
    }
    if (userIdx < 0) return;
    final text = _messages[userIdx].content;
    _messages.removeRange(userIdx, _messages.length);
    notifyListeners();
    await submitMessage(text);
  }

  void cancelActiveStream() {
    _activeStream?.call();
    _activeStream = null;
    _sending = false;
    notifyListeners();
  }

  Future<void> clearSession() async {
    _activeStream?.call();
    final sid = _sessionId;
    _sessionId = null;
    _contextAnalysisId = null;
    _messages.clear();
    _activeStream = null;
    _sending = false;
    notifyListeners();
    if (sid != null) {
      try {
        await _repo.deleteSession(sid);
      } catch (_) {}
    }
  }

  @override
  void dispose() {
    _activeStream?.call();
    super.dispose();
  }
}
