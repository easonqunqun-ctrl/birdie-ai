import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../data/models/chat.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../analysis/pages/report_page.dart';
import '../../auth/auth_controller.dart';
import '../chat_controller.dart';

const _kWelcomeText =
    '你好！我是领翼golf 的 AI 高尔夫教练。随时问我挥杆技术、练习方法或高尔夫知识方面的问题。';

/// AI 教练：对照 client/src/pages/coach/index。SSE 流式对话 + 快捷问题 + 三态。
class CoachPage extends StatefulWidget {
  const CoachPage({super.key, this.prefill, this.contextAnalysisId});

  /// 从报告页「问 AI 教练」带入的预填问题（只填入输入框，不自动发送）。
  final String? prefill;

  /// 从报告页带入的分析上下文 ID（会以「基于报告」建会话）。
  final String? contextAnalysisId;

  @override
  State<CoachPage> createState() => _CoachPageState();
}

class _CoachPageState extends State<CoachPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  bool _bootstrapped = false;

  @override
  void initState() {
    super.initState();
    if (widget.prefill != null && widget.prefill!.trim().isNotEmpty) {
      _input.text = widget.prefill!.trim();
    }
    _input.addListener(() => setState(() {}));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_bootstrapped) return;
      _bootstrapped = true;
      final ctl = context.read<ChatController>();
      final q = context.read<AuthController>().user?.quota;
      if (q != null) ctl.hydrateQuota(q.chatRemainingToday, q.chatTotalToday);
      ctl.bootstrapSession(contextAnalysisId: widget.contextAnalysisId);
    });
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    if (t.isEmpty) return;
    _input.clear();
    final ctl = context.read<ChatController>();
    _scrollToBottom();
    try {
      await ctl.submitMessage(t);
      _scrollToBottom();
    } on ChatSubmitException catch (e) {
      if (!mounted) return;
      final msg = switch (e.kind) {
        ChatErrorKind.quotaExhausted => '今日对话次数已用完',
        ChatErrorKind.rateLimit => '操作太快了，稍等片刻再试',
        _ => e.message,
      };
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  Future<void> _retry() async {
    try {
      await context.read<ChatController>().retryLast();
      _scrollToBottom();
    } on ChatSubmitException catch (_) {
      // 失败态已在气泡呈现
    }
  }

  Future<void> _confirmClear() async {
    final ctl = context.read<ChatController>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('清空对话？'),
        content: Text(ctl.sending
            ? '当前 AI 正在回复，点击清空会立即中断。'
            : '会删除本次会话的全部历史，AI 将以新会话身份开始。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, true), child: const Text('清空')),
        ],
      ),
    );
    if (ok != true) return;
    await ctl.clearSession();
    if (mounted) ctl.bootstrapSession();
  }

  @override
  Widget build(BuildContext context) {
    final ctl = context.watch<ChatController>();
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(
        title: const Text('AI 教练'),
        actions: [
          if (ctl.messages.isNotEmpty)
            IconButton(
                icon: const Icon(Icons.delete_outline), onPressed: _confirmClear),
        ],
      ),
      body: SafeArea(
        child: ctl.bootstrapError != null && ctl.messages.isEmpty
            ? _bootstrapErrorView(ctl)
            : Column(
                children: [
                  if (ctl.contextAnalysisId != null) _contextBanner(ctl),
                  Expanded(
                    child: ctl.loading && ctl.messages.isEmpty
                        ? _bootstrapLoading()
                        : _chatScroll(ctl),
                  ),
                  _quotaRow(ctl),
                  _inputBar(ctl),
                ],
              ),
      ),
    );
  }

  Widget _bootstrapLoading() => const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(BrandColors.primary)),
            SizedBox(height: 16),
            Text('正在接入 AI 教练...',
                style: TextStyle(color: BrandColors.textSecondary)),
          ],
        ),
      );

  Widget _bootstrapErrorView(ChatController ctl) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('😣', style: TextStyle(fontSize: rpx(80))),
            SizedBox(height: rpx(20)),
            Text(ctl.bootstrapError ?? '加载失败',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
            SizedBox(height: rpx(24)),
            OutlinedButton(
                onPressed: () => ctl.bootstrapSession(
                    contextAnalysisId: widget.contextAnalysisId),
                child: const Text('重新加载')),
          ],
        ),
      );

  Widget _contextBanner(ChatController ctl) => Container(
        width: double.infinity,
        color: BrandColors.primaryTint,
        padding: EdgeInsets.symmetric(horizontal: rpx(32), vertical: rpx(16)),
        child: Row(
          children: [
            Icon(Icons.description_outlined,
                size: rpx(32), color: BrandColors.primary),
            SizedBox(width: rpx(12)),
            Expanded(
              child: Text('基于报告的对话',
                  style: TextStyle(
                      fontSize: rpx(24), color: BrandColors.primaryDark)),
            ),
            GestureDetector(
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) =>
                      ReportPage(analysisId: ctl.contextAnalysisId!))),
              child: Text('查看原报告 ›',
                  style: TextStyle(
                      fontSize: rpx(24),
                      color: BrandColors.primary,
                      fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      );

  Widget _chatScroll(ChatController ctl) {
    final msgs = ctl.messages;
    return ListView(
      controller: _scroll,
      padding: EdgeInsets.all(rpx(32)),
      children: [
        _welcomeBubble(),
        for (final m in msgs) _bubble(m),
        if (msgs.isEmpty && ctl.quickQuestions.isNotEmpty) _quickQuestions(ctl),
      ],
    );
  }

  Widget _welcomeBubble() => _assistantWrap(
        child: Text(_kWelcomeText,
            style: TextStyle(
                fontSize: rpx(30),
                height: 1.55,
                color: BrandColors.textPrimary)),
      );

  Widget _quickQuestions(ChatController ctl) {
    final hasAnalysis =
        context.read<AuthController>().user?.hasCompletedRealAnalysis ?? false;
    return Padding(
      padding: EdgeInsets.only(top: rpx(24)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('试试这些问题：',
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.textSecondary)),
          SizedBox(height: rpx(20)),
          Wrap(
            spacing: rpx(16),
            runSpacing: rpx(16),
            children: [
              for (final q in ctl.quickQuestions)
                GestureDetector(
                  onTap: () {
                    if (q.requiresAnalysis && !hasAnalysis) {
                      _needAnalysisDialog();
                    } else {
                      _input.text = q.text;
                    }
                  },
                  child: Container(
                    padding: EdgeInsets.symmetric(
                        horizontal: rpx(28), vertical: rpx(18)),
                    decoration: BoxDecoration(
                      color: q.requiresAnalysis && !hasAnalysis
                          ? BrandColors.bgSubtle
                          : BrandColors.primaryTint,
                      borderRadius: BorderRadius.circular(rpx(32)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(q.text,
                            style: TextStyle(
                                fontSize: rpx(28),
                                color: q.requiresAnalysis && !hasAnalysis
                                    ? BrandColors.textTertiary
                                    : BrandColors.primaryDark)),
                        if (q.requiresAnalysis) ...[
                          SizedBox(width: rpx(10)),
                          Container(
                            padding: EdgeInsets.symmetric(
                                horizontal: rpx(10), vertical: rpx(2)),
                            decoration: BoxDecoration(
                              color: BrandColors.gold.withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(rpx(6)),
                            ),
                            child: Text('需分析',
                                style: TextStyle(
                                    fontSize: rpx(18),
                                    color: BrandColors.goldDark)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  void _needAnalysisDialog() {
    showDialog<void>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('需要先上传一次挥杆'),
        content: const Text('这个问题需要结合你的挥杆分析，先去「首页 → 开始分析」拍一次吧。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c), child: const Text('我知道了')),
        ],
      ),
    );
  }

  // -------------------- 气泡 --------------------
  Widget _bubble(ChatMessage m) {
    if (m.isUser) return _userBubble(m);
    return _assistantBubble(m);
  }

  Widget _userBubble(ChatMessage m) {
    final initial = (context.read<AuthController>().user?.nickname?.isNotEmpty ??
            false)
        ? context.read<AuthController>().user!.nickname!.characters.first
        : '我';
    return Padding(
      padding: EdgeInsets.only(bottom: rpx(24)),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Flexible(
            child: GestureDetector(
              onLongPress: () => _copy(m.content),
              child: Container(
                padding: EdgeInsets.symmetric(
                    horizontal: rpx(28), vertical: rpx(20)),
                decoration: BoxDecoration(
                  color: BrandColors.primary,
                  borderRadius: BorderRadius.circular(rpx(24)),
                ),
                child: Text(m.content,
                    style: TextStyle(
                        fontSize: rpx(30),
                        height: 1.55,
                        color: BrandColors.onPrimary)),
              ),
            ),
          ),
          SizedBox(width: rpx(16)),
          CircleAvatar(
            radius: rpx(36),
            backgroundColor: BrandColors.gold,
            child: Text(initial,
                style: const TextStyle(color: Colors.black, fontSize: 14)),
          ),
        ],
      ),
    );
  }

  Widget _assistantBubble(ChatMessage m) {
    final showTyping = m.streaming && m.content.isEmpty;
    return Padding(
      padding: EdgeInsets.only(bottom: rpx(24)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: rpx(36),
            backgroundColor: BrandColors.primaryTint,
            child: Icon(Icons.sports_golf,
                size: rpx(40), color: BrandColors.primary),
          ),
          SizedBox(width: rpx(16)),
          Flexible(
            child: GestureDetector(
              onLongPress: m.content.isEmpty ? null : () => _copy(m.content),
              onTap: m.errored ? _retry : null,
              child: Container(
                padding: EdgeInsets.symmetric(
                    horizontal: rpx(28), vertical: rpx(20)),
                decoration: BoxDecoration(
                  color: BrandColors.bgCard,
                  borderRadius: BorderRadius.circular(rpx(24)),
                  border: Border.all(
                      color: m.errored
                          ? BrandColors.error
                          : BrandColors.border),
                ),
                child: showTyping
                    ? _typing()
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text.rich(
                            TextSpan(children: [
                              TextSpan(text: m.content),
                              if (m.streaming)
                                const TextSpan(text: ' ▎'),
                            ]),
                            style: TextStyle(
                                fontSize: rpx(30),
                                height: 1.55,
                                color: m.errored
                                    ? BrandColors.error
                                    : BrandColors.textPrimary),
                          ),
                          if (m.errored) ...[
                            SizedBox(height: rpx(8)),
                            Text('↻ 点击重试',
                                style: TextStyle(
                                    fontSize: rpx(24),
                                    color: BrandColors.primary)),
                          ],
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _assistantWrap({required Widget child}) => Padding(
        padding: EdgeInsets.only(bottom: rpx(24)),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              radius: rpx(36),
              backgroundColor: BrandColors.primaryTint,
              child: Icon(Icons.sports_golf,
                  size: rpx(40), color: BrandColors.primary),
            ),
            SizedBox(width: rpx(16)),
            Flexible(
              child: Container(
                padding: EdgeInsets.symmetric(
                    horizontal: rpx(28), vertical: rpx(20)),
                decoration: BoxDecoration(
                  color: BrandColors.bgCard,
                  borderRadius: BorderRadius.circular(rpx(24)),
                  border: Border.all(color: BrandColors.border),
                ),
                child: child,
              ),
            ),
          ],
        ),
      );

  void _copy(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('已复制')));
  }

  Widget _typing() => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < 3; i++)
            Padding(
              padding: EdgeInsets.symmetric(horizontal: rpx(4)),
              child: Container(
                width: rpx(12),
                height: rpx(12),
                decoration: const BoxDecoration(
                    color: BrandColors.textTertiary, shape: BoxShape.circle),
              ),
            ),
        ],
      );

  // -------------------- 配额 + 输入 --------------------
  Widget _quotaRow(ChatController ctl) {
    final r = ctl.quotaRemaining;
    final t = ctl.quotaTotal;
    final quotaText = r < 0
        ? '会员无限次'
        : r == 0
            ? '今日已用完'
            : '今日剩余 $r/$t 次';
    final len = _input.text.characters.length;
    return Padding(
      padding: EdgeInsets.fromLTRB(rpx(32), rpx(8), rpx(32), 0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(quotaText,
              style: TextStyle(
                  fontSize: rpx(22), color: BrandColors.textTertiary)),
          Text('$len/500',
              style: TextStyle(
                  fontSize: rpx(22),
                  color: len > 500
                      ? BrandColors.error
                      : len > 450
                          ? BrandColors.warning
                          : BrandColors.textTertiary)),
        ],
      ),
    );
  }

  Widget _inputBar(ChatController ctl) {
    final exhausted = ctl.quotaRemaining == 0;
    return Container(
      padding: EdgeInsets.fromLTRB(rpx(24), rpx(12), rpx(24), rpx(16)),
      decoration: const BoxDecoration(
        color: BrandColors.bgCard,
        border: Border(top: BorderSide(color: BrandColors.border)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _input,
              minLines: 1,
              maxLines: 4,
              maxLength: 500,
              enabled: !ctl.sending && !exhausted,
              textInputAction: TextInputAction.send,
              onSubmitted: _send,
              decoration: InputDecoration(
                counterText: '',
                hintText: exhausted
                    ? '今日对话已用完'
                    : ctl.sending
                        ? 'AI 正在回复，稍等片刻...'
                        : '问问 AI 教练...',
                filled: true,
                fillColor: BrandColors.bgSubtle,
                isDense: true,
                contentPadding: EdgeInsets.symmetric(
                    horizontal: rpx(24), vertical: rpx(20)),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(rpx(28)),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          SizedBox(width: rpx(16)),
          ctl.sending
              ? GestureDetector(
                  onTap: () =>
                      context.read<ChatController>().cancelActiveStream(),
                  child: _circleBtn(Icons.stop, BrandColors.error),
                )
              : GestureDetector(
                  onTap: exhausted ? null : () => _send(_input.text),
                  child: _circleBtn(Icons.arrow_upward,
                      exhausted ? BrandColors.textTertiary : BrandColors.primary),
                ),
        ],
      ),
    );
  }

  Widget _circleBtn(IconData icon, Color color) => Container(
        width: rpx(80),
        height: rpx(80),
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        child: Icon(icon, color: BrandColors.onPrimary, size: rpx(40)),
      );
}
