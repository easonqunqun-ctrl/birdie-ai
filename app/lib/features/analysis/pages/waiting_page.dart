import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/swing_tips.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../analysis_controller.dart';
import 'capture_page.dart';
import 'report_page.dart';

/// 等待页用户可见的 5 个阶段（对照小程序 waiting.tsx STAGES）。
class _UiStage {
  final String key;
  final String label;
  const _UiStage(this.key, this.label);
}

const _uiStages = <_UiStage>[
  _UiStage('received', '视频已接收'),
  _UiStage('pose', '识别人体姿态'),
  _UiStage('swing', '分析挥杆动作'),
  _UiStage('diagnose', '生成诊断建议'),
  _UiStage('render', '渲染分析报告'),
];

// 后端 stage → UI 阶段索引
const _backendToUi = <String, int>{
  'preprocessing': 0,
  'pose_estimating': 1,
  'phase_segmenting': 2,
  'scoring': 2,
  'diagnosing': 3,
  'generating': 3,
};

/// 分析等待页：对照 client/src/pages/analysis/waiting。靛蓝主题 + 阶段清单 + 倒计时 + 小贴士。
class WaitingPage extends StatefulWidget {
  const WaitingPage({super.key, required this.analysisId});
  final String analysisId;

  @override
  State<WaitingPage> createState() => _WaitingPageState();
}

class _WaitingPageState extends State<WaitingPage> {
  final DateTime _startedAt = DateTime.now();
  int _elapsed = 0;
  int? _displaySeconds;
  int _tipIndex = 0;
  Timer? _ticker;
  Timer? _tipTimer;

  @override
  void initState() {
    super.initState();
    _tipIndex = (DateTime.now().millisecondsSinceEpoch ~/ 1000) % kSwingTips.length;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AnalysisController>().startPolling(
            widget.analysisId,
            onCompleted: _goReport,
            onFailed: (_) {},
          );
    });
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() {
        _elapsed = DateTime.now().difference(_startedAt).inSeconds;
        final server = context.read<AnalysisController>().remainingSeconds;
        if (server != null) {
          _displaySeconds = (_displaySeconds ?? server);
          if (_displaySeconds! > 0) _displaySeconds = _displaySeconds! - 1;
          // 服务端给出更小值时以服务端为准
          if (server < _displaySeconds!) _displaySeconds = server;
        }
      });
    });
    _tipTimer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (!mounted) return;
      setState(() => _tipIndex = (_tipIndex + 1) % kSwingTips.length);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _tipTimer?.cancel();
    super.dispose();
  }

  void _goReport() {
    if (!mounted) return;
    Future.delayed(const Duration(milliseconds: 250), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
            builder: (_) => ReportPage(analysisId: widget.analysisId)),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final ctl = context.watch<AnalysisController>();
    final failed = ctl.phase == AnalysisPhase.failed;
    return Scaffold(
      backgroundColor: BrandColors.primary,
      body: SafeArea(
        child: failed ? _failedView(ctl.error ?? '分析失败，请重试') : _loadingView(ctl),
      ),
    );
  }

  // -------------------- 进行中 --------------------
  Widget _loadingView(AnalysisController ctl) {
    final activeIdx = _backendToUi[ctl.stage] ?? 0;
    final completed = ctl.phase == AnalysisPhase.completed;
    final tip = kSwingTips[_tipIndex];
    return SingleChildScrollView(
      padding: EdgeInsets.symmetric(horizontal: rpx(48), vertical: rpx(40)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(height: rpx(24)),
          _spinner(),
          SizedBox(height: rpx(48)),
          Text(completed ? '分析完成' : 'AI 正在分析你的挥杆',
              style: TextStyle(
                  fontSize: rpx(44),
                  fontWeight: FontWeight.w800,
                  color: Colors.white)),
          SizedBox(height: rpx(16)),
          Text(
              completed
                  ? '即将为你打开报告…'
                  : (_displaySeconds != null && _displaySeconds! > 0
                      ? '预计还需 $_displaySeconds 秒'
                      : '预计还需不到 30 秒'),
              style: TextStyle(fontSize: rpx(28), color: Colors.white70)),
          if (_elapsed >= 60 && _elapsed < 120) ...[
            SizedBox(height: rpx(28)),
            _softBanner(),
          ],
          SizedBox(height: rpx(48)),
          _checklist(activeIdx, completed),
          if (_elapsed >= 120) ...[
            SizedBox(height: rpx(40)),
            _timeoutBlock(),
          ],
          SizedBox(height: rpx(48)),
          _tipCard(tip),
        ],
      ),
    );
  }

  Widget _spinner() => SizedBox(
        width: rpx(160),
        height: rpx(160),
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox(
              width: rpx(160),
              height: rpx(160),
              child: CircularProgressIndicator(
                strokeWidth: rpx(8),
                backgroundColor: Colors.white24,
                valueColor:
                    const AlwaysStoppedAnimation<Color>(BrandColors.gold),
              ),
            ),
            Text('AI',
                style: TextStyle(
                    fontSize: rpx(44),
                    fontWeight: FontWeight.w900,
                    color: BrandColors.gold)),
          ],
        ),
      );

  Widget _checklist(int activeIdx, bool completed) {
    return Column(
      children: [
        for (var i = 0; i < _uiStages.length; i++)
          _stageRow(_uiStages[i].label,
              done: completed || i < activeIdx,
              active: !completed && i == activeIdx),
      ],
    );
  }

  Widget _stageRow(String label, {required bool done, required bool active}) {
    final color = done
        ? BrandColors.gold
        : active
            ? Colors.white
            : Colors.white38;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: rpx(12)),
      child: Row(
        children: [
          Container(
            width: rpx(40),
            height: rpx(40),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: done
                  ? BrandColors.gold
                  : active
                      ? Colors.white24
                      : Colors.transparent,
              border: Border.all(
                  color: done ? BrandColors.gold : Colors.white38, width: 1.5),
            ),
            child: done
                ? const Icon(Icons.check, size: 16, color: Colors.black)
                : active
                    ? SizedBox(
                        width: rpx(20),
                        height: rpx(20),
                        child: const CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : null,
          ),
          SizedBox(width: rpx(24)),
          Text(label,
              style: TextStyle(
                  fontSize: rpx(30),
                  color: color,
                  fontWeight: active ? FontWeight.w700 : FontWeight.w400)),
        ],
      ),
    );
  }

  Widget _softBanner() => Container(
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(Radii.md),
        ),
        child: Text('分析可能比预期稍久，请耐心等待；仍可留在本页或稍后在「我的分析报告」查看结果。',
            style: TextStyle(
                fontSize: rpx(24), height: 1.5, color: Colors.white70)),
      );

  Widget _timeoutBlock() => Container(
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: BrandColors.warning.withValues(alpha: 0.6)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('⏳ 分析时间比预期长',
                style: TextStyle(
                    fontSize: rpx(30),
                    fontWeight: FontWeight.w700,
                    color: Colors.white)),
            SizedBox(height: rpx(12)),
            Text('别担心，任务还在后台跑。完成后你可以在「我的分析报告」里查看结果。你也可以先去首页做点别的。',
                style: TextStyle(
                    fontSize: rpx(24), height: 1.5, color: Colors.white70)),
            SizedBox(height: rpx(20)),
            OutlinedButton(
              onPressed: () =>
                  Navigator.of(context).popUntil((r) => r.isFirst),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white54),
              ),
              child: const Text('先回首页'),
            ),
          ],
        ),
      );

  Widget _tipCard(SwingTip tip) => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(Radii.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${tip.category}  ·  你知道吗？',
                style: TextStyle(
                    fontSize: rpx(24),
                    color: BrandColors.gold,
                    fontWeight: FontWeight.w700)),
            SizedBox(height: rpx(16)),
            Text(tip.text,
                style: TextStyle(
                    fontSize: rpx(28), height: 1.6, color: Colors.white)),
          ],
        ),
      );

  // -------------------- 失败 --------------------
  Widget _failedView(String msg) {
    return Center(
      child: SingleChildScrollView(
        padding: EdgeInsets.all(rpx(48)),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('😣', style: TextStyle(fontSize: rpx(96))),
            SizedBox(height: rpx(24)),
            Text('分析失败',
                style: TextStyle(
                    fontSize: rpx(44),
                    fontWeight: FontWeight.w800,
                    color: Colors.white)),
            SizedBox(height: rpx(16)),
            Text(msg,
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: rpx(28), height: 1.5, color: Colors.white70)),
            SizedBox(height: rpx(56)),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).pushReplacement(
                    MaterialPageRoute(builder: (_) => const CapturePage())),
                style: ElevatedButton.styleFrom(
                  backgroundColor: BrandColors.gold,
                  foregroundColor: Colors.black,
                  padding: EdgeInsets.symmetric(vertical: rpx(24)),
                ),
                child: const Text('重新拍摄'),
              ),
            ),
            SizedBox(height: rpx(20)),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white54),
                  padding: EdgeInsets.symmetric(vertical: rpx(24)),
                ),
                child: const Text('去首页'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
