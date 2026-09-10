import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:video_player/video_player.dart';

import '../../../core/analysis_options.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/primary_button.dart';
import '../../../l10n/l10n.dart';
import 'params_page.dart';
import 'report_page.dart';

/// 拍摄/选片页：对照 client capture → 选好视频后进 params。
class CapturePage extends StatefulWidget {
  const CapturePage({super.key});

  @override
  State<CapturePage> createState() => _CapturePageState();
}

class _CapturePageState extends State<CapturePage> {
  final _picker = ImagePicker();
  XFile? _video;
  double _duration = 0;
  int _size = 0;
  bool _preparing = false;

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _pick(ImageSource source) async {
    final l10n = context.l10n;
    setState(() => _preparing = true);
    try {
      final x = await _picker.pickVideo(
        source: source,
        maxDuration: const Duration(seconds: kMaxDurationSeconds),
      );
      if (x == null) return;
      final ext = x.path.split('.').last.toLowerCase();
      if (!kAcceptedExtensions.contains(ext)) {
        _toast(l10n.captureOnlyMp4Mov);
        return;
      }
      final size = await File(x.path).length();
      if (size > kMaxSizeBytes) {
        _toast(l10n.captureTooLarge);
        return;
      }
      final dur = await _readDuration(x.path);
      if (dur < kMinDurationSeconds) {
        _toast(l10n.captureTooShort(kMinDurationSeconds));
        return;
      }
      if (dur > kMaxDurationSeconds + 1) {
        _toast(l10n.captureTooLong(kMaxDurationSeconds));
        return;
      }
      setState(() {
        _video = x;
        _duration = dur;
        _size = size;
      });
    } catch (e) {
      _toast(l10n.capturePickFailed('$e'));
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

  void _next() {
    if (_video == null) {
      _toast(context.l10n.captureNeedVideo);
      return;
    }
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ParamsPage(
        filePath: _video!.path,
        fileSize: _size,
        duration: _duration,
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.captureTitle)),
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
              context.l10n.captureLimits(
                kMinDurationSeconds,
                kMaxDurationSeconds,
                (kMaxSizeBytes / 1024 / 1024).round(),
                kAcceptedExtensions.join(' / ').toUpperCase(),
              ),
              style: TextStyle(
                  fontSize: rpx(22), color: BrandColors.textTertiary),
            ),
            SizedBox(height: rpx(48)),
            PrimaryButton(
              label: context.l10n.captureNextParams,
              disabled: _video == null,
              onTap: _next,
            ),
            SizedBox(height: rpx(20)),
            Center(
              child: GestureDetector(
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const ReportPage(analysisId: 'sample'))),
                child: Text(context.l10n.captureTrySample,
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
            Text(context.l10n.captureCenterSubject,
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
          ],
        ),
      );

  List<(String, String)> get _captureTips => [
        ('📐', context.l10n.captureTipFraming),
        ('🎬', context.l10n.captureTipLength),
        ('💡', context.l10n.captureTipLight),
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
                Text(context.l10n.capturePrompt,
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
                    context.l10n.captureSelected(
                      _duration.toStringAsFixed(1),
                      (_size / 1024 / 1024).toStringAsFixed(1),
                    ),
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
                    Icons.videocam, context.l10n.record, () => _pick(ImageSource.camera)),
              ),
              SizedBox(width: rpx(20)),
              Expanded(
                child: _pickBtn(Icons.photo_library_outlined, context.l10n.album,
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
}
