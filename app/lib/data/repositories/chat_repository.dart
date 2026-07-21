// 条件 map 条目（if (x != null) 'k': x）无法改写成 ?'k': x（? 作用于 key 非 value）。
// ignore_for_file: use_null_aware_elements
import '../../core/api_client.dart';
import '../../core/sse_client.dart';
import '../models/chat.dart';

// 业务错误码（对齐 docs/02 + chatStore）
const kErrChatQuotaExhausted = 40007;
const kErrRateLimit = 40009;
const kErrContentViolation = 40017;
const kErrChatService = 50106;

/// SSE 事件回调集合，对照 chatService.StreamHandlers。
class ChatStreamHandlers {
  final void Function(String userMessageId, String assistantMessageId,
      Map<String, dynamic> userMessage) onStart;
  final void Function(String delta) onDelta;
  final void Function(Map<String, dynamic> attachment) onAttachment;
  final void Function(String assistantMessageId, String content,
      List<Map<String, dynamic>> attachments, int quotaRemaining) onEnd;
  final void Function(int code, String message) onBusinessError;
  final void Function(Object err, {required bool aborted}) onTransportError;
  final void Function() onClose;

  const ChatStreamHandlers({
    required this.onStart,
    required this.onDelta,
    required this.onAttachment,
    required this.onEnd,
    required this.onBusinessError,
    required this.onTransportError,
    required this.onClose,
  });
}

/// AI 对话域仓库：对照 client/src/services/chatService.ts。
class ChatRepository {
  ChatRepository(this._api);
  final ApiClient _api;

  Future<List<QuickQuestion>> getQuickQuestions() async {
    try {
      final data = await _api.get<Map<String, dynamic>>(
        '/chat/quick-questions',
        noAuth: true,
        timeout: const Duration(seconds: 60),
      );
      return (data['questions'] as List?)
              ?.map((e) => QuickQuestion.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [];
    } catch (_) {
      return const [];
    }
  }

  Future<CreateSessionResult> createSession({String? contextAnalysisId}) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/chat/sessions',
      data: {
        if (contextAnalysisId != null) 'context_analysis_id': contextAnalysisId,
      },
      timeout: const Duration(seconds: 60),
    );
    return CreateSessionResult.fromJson(data);
  }

  Future<List<ChatMessage>> getMessages(String sessionId,
      {int page = 1, int pageSize = 100}) async {
    final data = await _api.get<Map<String, dynamic>>(
      '/chat/sessions/$sessionId/messages?page=$page&page_size=$pageSize',
      timeout: const Duration(seconds: 60),
    );
    return (data['items'] as List?)
            ?.map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const [];
  }

  Future<void> deleteSession(String sessionId) =>
      _api.del('/chat/sessions/$sessionId', timeout: const Duration(seconds: 30));

  /// 流式发送。返回 cancel 函数。
  SseCancel streamMessage(
    String sessionId,
    String content,
    ChatStreamHandlers h,
  ) {
    return streamSse(
      path: '/chat/sessions/$sessionId/messages?stream=true',
      body: {'content': content},
      onEvent: (type, data) {
        switch (type) {
          case 'message_start':
            h.onStart(
              data['user_message_id']?.toString() ?? '',
              data['assistant_message_id']?.toString() ?? '',
              (data['user_message'] as Map?)?.cast<String, dynamic>() ?? {},
            );
            break;
          case 'content_delta':
            h.onDelta(data['delta']?.toString() ?? '');
            break;
          case 'attachment':
            final att = (data['attachment'] as Map?)?.cast<String, dynamic>();
            if (att != null) h.onAttachment(att);
            break;
          case 'message_end':
            h.onEnd(
              data['assistant_message_id']?.toString() ?? '',
              data['content']?.toString() ?? '',
              (data['attachments'] as List?)
                      ?.whereType<Map>()
                      .map((e) => e.cast<String, dynamic>())
                      .toList() ??
                  const [],
              (data['quota_remaining'] as num?)?.toInt() ?? -1,
            );
            h.onClose();
            break;
          case 'error':
            h.onBusinessError(
              (data['code'] as num?)?.toInt() ?? kErrChatService,
              data['message']?.toString() ?? 'AI 教练暂时不可用',
            );
            break;
          // message / ping 忽略
        }
      },
      onError: (err, {required aborted}) =>
          h.onTransportError(err, aborted: aborted),
      onDone: h.onClose,
    );
  }
}
