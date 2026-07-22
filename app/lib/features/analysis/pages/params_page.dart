import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/analysis_options.dart';
import '../../../core/sanitize_swing_candidates.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/primary_button.dart';
import '../analysis_controller.dart';
import 'select_swing_page.dart';
import 'waiting_page.dart';

/// 分析参数页：球杆 / 机位 → 上传 →（可选选段）→ waiting。
/// 对照 client/src/pages/analysis/params.tsx（精简版：无质量预检/模式切换）。
class ParamsPage extends StatefulWidget {
  const ParamsPage({
    super.key,
    required this.filePath,
    required this.fileSize,
    required this.duration,
  });

  final String filePath;
  final int fileSize;
  final double duration;

  @override
  State<ParamsPage> createState() => _ParamsPageState();
}

class _ParamsPageState extends State<ParamsPage> {
  String _mode = 'full_swing'; // full_swing | putting | chipping
  String _clubType = 'iron_7';
  String _cameraAngle = 'face_on';
  String _statusHint = '';

  static const _modes = <(String, String, String)>[
    ('full_swing', '全挥杆', '铁木杆 / 一号木'),
    ('putting', '推杆', '果岭推杆'),
    ('chipping', '切杆', '短切 / 劈起'),
  ];

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  String _formatSize(int bytes) {
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)}KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)}MB';
  }

  void _onModeChanged(String mode) {
    setState(() {
      _mode = mode;
      if (mode == 'putting' && _clubType != 'putter') {
        _clubType = 'putter';
      } else if (mode == 'chipping' &&
          !(_clubType.contains('wedge') ||
              _clubType == 'pw' ||
              _clubType == 'sw' ||
              _clubType == 'lw')) {
        _clubType = 'pw';
      } else if (mode == 'full_swing' && _clubType == 'putter') {
        _clubType = 'iron_7';
      }
    });
  }

  Future<void> _submit() async {
    final ctl = context.read<AnalysisController>();
    ctl.reset();
    setState(() => _statusHint = '上传中…');
    try {
      final token = await ctl.uploadOnly(
        filePath: widget.filePath,
        fileSize: widget.fileSize,
        duration: widget.duration,
      );
      if (!mounted) return;

      // putting / chipping 跳过选段（对齐 docs/02）
      if (_mode == 'full_swing') {
        setState(() => _statusHint = '识别挥杆段…');
        final detected = await ctl.tryDetectSwings(token.uploadId);
        if (!mounted) return;

        if (detected != null) {
          final angle = detected.suggestedCameraAngle;
          if (angle != null &&
              (angle == 'face_on' || angle == 'down_the_line')) {
            setState(() => _cameraAngle = angle);
          }
          final needSelect = ctl.stagePendingIfMulti(
            token: token,
            detected: detected,
            cameraAngle: _cameraAngle,
            clubType: _clubType,
            mode: _mode,
            duration: widget.duration,
            size: widget.fileSize,
          );
          if (needSelect) {
            setState(() => _statusHint = '');
            Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => SelectSwingPage(uploadId: token.uploadId),
            ));
            return;
          }
          final sanitized = sanitizeSwingCandidates(
            detected.swingCandidates,
            detected.defaultSelectedIndex,
          );
          setState(() => _statusHint = '创建分析任务…');
          final id = await ctl.createAnalysisTask(
            uploadId: token.uploadId,
            cameraAngle: _cameraAngle,
            clubType: _clubType,
            mode: _mode,
            selectedSwingIndex: sanitized.candidates.length == 1
                ? sanitized.defaultIndex
                : null,
          );
          if (!mounted) return;
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => WaitingPage(analysisId: id)),
          );
          return;
        }
      }

      setState(() => _statusHint = '创建分析任务…');
      final id = await ctl.createAnalysisTask(
        uploadId: token.uploadId,
        cameraAngle: _cameraAngle,
        clubType: _clubType,
        mode: _mode,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => WaitingPage(analysisId: id)),
      );
    } catch (_) {
      _toast(ctl.error ?? '发起分析失败');
      if (mounted) setState(() => _statusHint = '');
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = context.watch<AnalysisController>().busy;
    final progress = context.watch<AnalysisController>().uploadProgress;
    final bottom = MediaQuery.of(context).padding.bottom;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('分析参数')),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(rpx(32), rpx(24), rpx(32), rpx(32)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _videoMeta(),
                  SizedBox(height: rpx(32)),
                  _sectionTitle('分析模式'),
                  SizedBox(height: rpx(16)),
                  _modeSelector(),
                  if (_mode != 'full_swing') ...[
                    SizedBox(height: rpx(8)),
                    Text('推杆/切杆需服务端灰度开启；若创建失败请改回全挥杆。',
                        style: TextStyle(
                            fontSize: rpx(22),
                            color: BrandColors.textTertiary)),
                  ],
                  SizedBox(height: rpx(32)),
                  _sectionTitle('球杆'),
                  SizedBox(height: rpx(16)),
                  _clubSelector(),
                  SizedBox(height: rpx(32)),
                  _sectionTitle('拍摄机位'),
                  SizedBox(height: rpx(16)),
                  _angleSelector(),
                  if (_statusHint.isNotEmpty) ...[
                    SizedBox(height: rpx(32)),
                    Text(
                      busy && progress > 0 && progress < 1
                          ? '$_statusHint ${(progress * 100).round()}%'
                          : _statusHint,
                      style: TextStyle(
                          fontSize: rpx(26), color: BrandColors.primary),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Container(
            width: double.infinity,
            padding: EdgeInsets.fromLTRB(
                rpx(32), rpx(16), rpx(32), bottom + rpx(16)),
            decoration: const BoxDecoration(
              color: BrandColors.bgCard,
              border: Border(top: BorderSide(color: BrandColors.border)),
            ),
            child: PrimaryButton(
              label: busy ? '处理中…' : '开始分析',
              loading: busy,
              height: rpx(88),
              onTap: _submit,
            ),
          ),
        ],
      ),
    );
  }

  Widget _videoMeta() => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Row(
          children: [
            Icon(Icons.videocam, color: BrandColors.primary, size: rpx(44)),
            SizedBox(width: rpx(16)),
            Expanded(
              child: Text(
                '已选视频 · ${widget.duration.toStringAsFixed(1)}s · ${_formatSize(widget.fileSize)}',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textPrimary),
              ),
            ),
          ],
        ),
      );

  Widget _sectionTitle(String t) => Text(t,
      style: TextStyle(
          fontSize: rpx(32),
          fontWeight: FontWeight.w700,
          color: BrandColors.textPrimary));

  Widget _modeSelector() => Column(
        children: [
          for (final m in _modes)
            Padding(
              padding: EdgeInsets.only(bottom: rpx(12)),
              child: GestureDetector(
                onTap: () => _onModeChanged(m.$1),
                child: Container(
                  width: double.infinity,
                  padding: EdgeInsets.symmetric(
                      horizontal: rpx(24), vertical: rpx(20)),
                  decoration: BoxDecoration(
                    color: _mode == m.$1
                        ? BrandColors.primaryTint
                        : BrandColors.bgCard,
                    borderRadius: BorderRadius.circular(Radii.md),
                    border: Border.all(
                        color: _mode == m.$1
                            ? BrandColors.primary
                            : BrandColors.border,
                        width: _mode == m.$1 ? 2 : 1),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.$2,
                                style: TextStyle(
                                    fontSize: rpx(30),
                                    fontWeight: FontWeight.w700,
                                    color: BrandColors.primary)),
                            Text(m.$3,
                                style: TextStyle(
                                    fontSize: rpx(24),
                                    color: BrandColors.textTertiary)),
                          ],
                        ),
                      ),
                      if (_mode == m.$1)
                        const Icon(Icons.check_circle,
                            color: BrandColors.primary),
                    ],
                  ),
                ),
              ),
            ),
        ],
      );

  Widget _clubSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final group in clubTypeGroups) ...[
          Padding(
            padding: EdgeInsets.only(bottom: rpx(12)),
            child: Text(group.title,
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.textSecondary)),
          ),
          Wrap(
            spacing: rpx(16),
            runSpacing: rpx(16),
            children: [
              for (final c in group.items)
                _chip(clubTypeLabels[c] ?? c, _clubType == c,
                    () => setState(() => _clubType = c)),
            ],
          ),
          SizedBox(height: rpx(20)),
        ],
      ],
    );
  }

  Widget _angleSelector() {
    return Row(
      children: [
        for (final a in cameraAngleLabels.keys)
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(right: a == 'face_on' ? rpx(16) : 0),
              child: GestureDetector(
                onTap: () => setState(() => _cameraAngle = a),
                child: Container(
                  padding: EdgeInsets.symmetric(vertical: rpx(24)),
                  decoration: BoxDecoration(
                    color: _cameraAngle == a
                        ? BrandColors.primaryTint
                        : BrandColors.bgCard,
                    borderRadius: BorderRadius.circular(Radii.md),
                    border: Border.all(
                        color: _cameraAngle == a
                            ? BrandColors.primary
                            : BrandColors.border,
                        width: _cameraAngle == a ? 2 : 1),
                  ),
                  child: Column(
                    children: [
                      Text(cameraAngleLabels[a]!,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(28),
                              fontWeight: FontWeight.w600,
                              color: _cameraAngle == a
                                  ? BrandColors.primary
                                  : BrandColors.textPrimary)),
                      SizedBox(height: rpx(6)),
                      Text(cameraAngleDesc[a]!,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(22),
                              color: BrandColors.textSecondary)),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _chip(String label, bool active, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(16)),
        decoration: BoxDecoration(
          color: active ? BrandColors.primary : BrandColors.bgCard,
          borderRadius: BorderRadius.circular(rpx(32)),
          border: Border.all(
              color: active ? BrandColors.primary : BrandColors.border),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: rpx(28),
                color:
                    active ? BrandColors.onPrimary : BrandColors.textPrimary)),
      ),
    );
  }
}
