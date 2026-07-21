// AI 对话 DTO：对照 client/src/types/chat.ts。
// ChatMessage 为可变对象，便于 SSE 逐字追加 content 与切换 streaming/errored 态。

class ChatMessage {
  String id;
  final String role; // user / assistant / system
  String content;
  List<Map<String, dynamic>> attachments;
  final String createdAt;

  // transient 渲染态（不参与发往后端的 payload）
  bool streaming;
  bool errored;
  bool pending;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.attachments = const [],
    required this.createdAt,
    this.streaming = false,
    this.errored = false,
    this.pending = false,
  });

  bool get isUser => role == 'user';

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        id: j['id']?.toString() ?? '',
        role: j['role']?.toString() ?? 'assistant',
        content: j['content']?.toString() ?? '',
        attachments: (j['attachments'] as List?)
                ?.whereType<Map>()
                .map((e) => e.cast<String, dynamic>())
                .toList() ??
            const [],
        createdAt: j['created_at']?.toString() ?? '',
      );
}

class QuickQuestion {
  final String id;
  final String text;
  final bool requiresAnalysis;
  const QuickQuestion(
      {required this.id, required this.text, this.requiresAnalysis = false});

  factory QuickQuestion.fromJson(Map<String, dynamic> j) => QuickQuestion(
        id: j['id']?.toString() ?? '',
        text: j['text']?.toString() ?? '',
        requiresAnalysis: j['requires_analysis'] == true,
      );
}

class CreateSessionResult {
  final String sessionId;
  final String? contextAnalysisId;
  final List<ChatMessage> messages;

  const CreateSessionResult({
    required this.sessionId,
    this.contextAnalysisId,
    this.messages = const [],
  });

  factory CreateSessionResult.fromJson(Map<String, dynamic> j) =>
      CreateSessionResult(
        sessionId: j['session_id']?.toString() ?? '',
        contextAnalysisId: j['context_analysis_id'] as String?,
        messages: (j['messages'] as List?)
                ?.map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
      );
}

/// 发送态错误类别，对照 chatStore SubmitMessageError。
enum ChatErrorKind {
  quotaExhausted,
  rateLimit,
  contentViolation,
  serviceError,
  network,
}

class ChatSubmitException implements Exception {
  final ChatErrorKind kind;
  final String message;
  ChatSubmitException(this.kind, this.message);
  @override
  String toString() => message;
}
