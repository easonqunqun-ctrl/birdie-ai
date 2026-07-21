import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../../../core/analysis_options.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/primary_button.dart';
import '../analysis_controller.dart';
import 'waiting_page.dart';
import 'report_page.dart';

/// 拍摄/选片页：对照 client/src/pages/analysis/capture。
/// M1 视频预检简化：只校验时长(2-30s)/大小(≤100MB)/扩展名。
class CapturePage extends StatefulWidget {
  const CapturePage({super.key});

  @override
  State<CapturePage> createState() => _CapturePageState();
}

class _CapturePageState extends State<CapturePage> {
  final _picker = ImagePicker();
  String _clubType = 'iron_7';
  String _cameraAngle = 'face_on';
  XFile? _video;
  double _duration = 0;
  int _size = 0;
  bool _preparing = false;

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _pick(ImageSource source) async {
    setState(() => _preparing = true);
    try {
      final x = await _picker.pickVideo(
        source: source,
        maxDuration: const Duration(seconds: kMaxDurationSeconds),
      );
      if (x == null) return;
      final ext = x.path.split('.').last.toLowerCase();
      if (!kAcceptedExtensions.contains(ext)) {
        _toast('仅支持 mp4 / mov 视频');
        return;
      }
      final size = await File(x.path).length();
      if (size > kMaxSizeBytes) {
        _toast('视频不能超过 100MB');
        return;
      }
      final dur = await _readDuration(x.path);
      if (dur < kMinDurationSeconds) {
        _toast('视频太短（需 ≥ ${kMinDurationSeconds}s）');
        return;
      }
      if (dur > kMaxDurationSeconds + 1) {
        _toast('视频太长（需 ≤ ${kMaxDurationSeconds}s）');
        return;
      }
      setState(() {
        _video = x;
        _duration = dur;
        _size = size;
      });
    } catch (e) {
      _toast('选取视频失败：$e');
    } finally {
      if (mounted) setState(() => _preparing = false);
    }
  }

  Future<double> _readDuration(String path) async {
    final c = VideoPlayerController.file(File(path));
    try {
      await c.initialize();
      return c.value.duration.inMilliseconds / 1000.0;
    } finally {
      await c.dispose();
    }
  }

  Future<void> _start() async {
    if (_video == null) {
      _toast('请先拍摄或选择挥杆视频');
      return;
    }
    final ctl = context.read<AnalysisController>();
    ctl.reset();
    try {
      final id = await ctl.startAnalysis(
        filePath: _video!.path,
        fileSize: _size,
        duration: _duration,
        cameraAngle: _cameraAngle,
        clubType: _clubType,
      );
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => WaitingPage(analysisId: id)),
      );
    } catch (e) {
      _toast(ctl.error ?? '发起分析失败');
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = context.watch<AnalysisController>().busy;
    return Scaffold(
      appBar: AppBar(title: const Text('挥杆分析')),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(rpx(32)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _guideHero(),
            SizedBox(height: rpx(24)),
            _tips(),
            SizedBox(height: rpx(32)),
            _videoCard(),
            SizedBox(height: rpx(16)),
            Text(
              '时长 $kMinDurationSeconds-$kMaxDurationSeconds s · 大小 ≤ ${(kMaxSizeBytes / 1024 / 1024).round()}MB · 支持 ${kAcceptedExtensions.join(' / ').toUpperCase()}',
              style: TextStyle(
                  fontSize: rpx(22), color: BrandColors.textTertiary),
            ),
            SizedBox(height: rpx(32)),
            _sectionTitle('球杆'),
            SizedBox(height: rpx(16)),
            _clubSelector(),
            SizedBox(height: rpx(32)),
            _sectionTitle('拍摄机位'),
            SizedBox(height: rpx(16)),
            _angleSelector(),
            SizedBox(height: rpx(48)),
            PrimaryButton(
              label: '开始分析',
              loading: busy,
              disabled: _video == null,
              onTap: _start,
            ),
            SizedBox(height: rpx(20)),
            Center(
              child: GestureDetector(
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const ReportPage(analysisId: 'sample'))),
                child: Text('先用示例视频体验一下',
                    style: TextStyle(
                        fontSize: rpx(28),
                        color: BrandColors.primary,
                        decoration: TextDecoration.underline)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String t) => Text(t,
      style: TextStyle(
          fontSize: rpx(32),
          fontWeight: FontWeight.w700,
          color: BrandColors.textPrimary));

  Widget _guideHero() => Container(
        width: double.infinity,
        padding: EdgeInsets.symmetric(vertical: rpx(40)),
        decoration: BoxDecoration(
          gradient: BrandColors.gradientHero,
          borderRadius: BorderRadius.circular(Radii.lg),
        ),
        child: Column(
          children: [
            Container(
              width: rpx(150),
              height: rpx(200),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white70, width: 2),
                borderRadius: BorderRadius.circular(rpx(12)),
              ),
              child: Text('🏌️', style: TextStyle(fontSize: rpx(72))),
            ),
            SizedBox(height: rpx(16)),
            Text('对准人物 · 居中入画',
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
          ],
        ),
      );

  static const _captureTips = [
    ('📐', '将球员放在画面中央，脚到头部全部露出'),
    ('🎬', '拍满至少 2 秒（建议 3–5 秒），只录 1 次完整挥杆'),
    ('💡', '优选自然光，避免强背光和严重抖动'),
  ];

  Widget _tips() => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final t in _captureTips)
              Padding(
                padding: EdgeInsets.symmetric(vertical: rpx(8)),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(t.$1, style: TextStyle(fontSize: rpx(30))),
                    SizedBox(width: rpx(16)),
                    Expanded(
                      child: Text(t.$2,
                          style: TextStyle(
                              fontSize: rpx(26),
                              height: 1.5,
                              color: BrandColors.textSecondary)),
                    ),
                  ],
                ),
              ),
          ],
        ),
      );

  Widget _videoCard() {
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(32)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          if (_video == null)
            Column(
              children: [
                Icon(Icons.videocam_outlined,
                    size: rpx(96), color: BrandColors.textTertiary),
                SizedBox(height: rpx(16)),
                Text('拍摄或选择一段挥杆视频（2-30 秒）',
                    style: TextStyle(
                        fontSize: rpx(28), color: BrandColors.textSecondary)),
              ],
            )
          else
            Row(
              children: [
                Icon(Icons.check_circle,
                    color: BrandColors.success, size: rpx(48)),
                SizedBox(width: rpx(16)),
                Expanded(
                  child: Text(
                    '已选择 · ${_duration.toStringAsFixed(1)}s · ${(_size / 1024 / 1024).toStringAsFixed(1)}MB',
                    style: TextStyle(
                        fontSize: rpx(28), color: BrandColors.textPrimary),
                  ),
                ),
              ],
            ),
          SizedBox(height: rpx(24)),
          Row(
            children: [
              Expanded(
                child: _pickBtn(
                    Icons.videocam, '录制', () => _pick(ImageSource.camera)),
              ),
              SizedBox(width: rpx(20)),
              Expanded(
                child: _pickBtn(Icons.photo_library_outlined, '相册',
                    () => _pick(ImageSource.gallery)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _pickBtn(IconData icon, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: _preparing ? null : onTap,
      child: Container(
        height: rpx(88),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: BrandColors.primaryTint,
          borderRadius: BorderRadius.circular(Radii.md),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: BrandColors.primary, size: rpx(40)),
            SizedBox(width: rpx(12)),
            Text(label,
                style: TextStyle(
                    fontSize: rpx(30),
                    color: BrandColors.primary,
                    fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

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
                color: active ? BrandColors.onPrimary : BrandColors.textPrimary)),
      ),
    );
  }
}
