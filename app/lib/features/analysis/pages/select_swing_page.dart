import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../data/models/analysis.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/primary_button.dart';
import '../analysis_controller.dart';
import 'waiting_page.dart';

/// 多挥选段：对照 client/src/pages/analysis/select-swing。
class SelectSwingPage extends StatefulWidget {
  const SelectSwingPage({super.key, required this.uploadId});
  final String uploadId;

  @override
  State<SelectSwingPage> createState() => _SelectSwingPageState();
}

class _SelectSwingPageState extends State<SelectSwingPage> {
  int _selected = 0;
  bool _submitting = false;
  bool _invalid = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pending = context.read<AnalysisController>().pendingSwing;
      if (pending == null || pending.uploadId != widget.uploadId) {
        setState(() => _invalid = true);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('选段信息已失效，请重新上传')),
        );
        Future.delayed(const Duration(milliseconds: 800), () {
          if (mounted) Navigator.of(context).pop();
        });
        return;
      }
      setState(() => _selected = pending.defaultSelectedIndex);
    });
  }

  String _fmtTime(double sec) {
    final safe = sec < 0 ? 0.0 : sec;
    if (safe < 10) return '${safe.toStringAsFixed(1)}s';
    final total = safe.floor();
    final m = total ~/ 60;
    final s = total % 60;
    return '$m:${s.toString().padLeft(2, '0')}';
  }

  Future<void> _confirm(PendingSwingSelection pending) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    final ctl = context.read<AnalysisController>();
    try {
      final id = await ctl.createAnalysisTask(
        uploadId: pending.uploadId,
        cameraAngle: pending.cameraAngle,
        clubType: pending.clubType,
        mode: pending.mode,
        targetYardage: pending.targetYardage,
        selectedSwingIndex: _selected,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => WaitingPage(analysisId: id)),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ctl.error ?? '创建失败')),
      );
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pending = context.watch<AnalysisController>().pendingSwing;
    if (_invalid || pending == null || pending.uploadId != widget.uploadId) {
      return const Scaffold(body: SizedBox.shrink());
    }
    final list = pending.swingCandidates;
    final bottom = MediaQuery.of(context).padding.bottom;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('选择挥杆段')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: EdgeInsets.all(rpx(32)),
              children: [
                Text('检测到 ${list.length} 段挥杆',
                    style: TextStyle(
                        fontSize: rpx(36),
                        fontWeight: FontWeight.w700,
                        color: BrandColors.textPrimary)),
                SizedBox(height: rpx(8)),
                Text('请选择要分析的一段。试挥段已标注，默认选中第一段正式挥杆。',
                    style: TextStyle(
                        fontSize: rpx(26),
                        height: 1.45,
                        color: BrandColors.textSecondary)),
                SizedBox(height: rpx(24)),
                for (var i = 0; i < list.length; i++)
                  _item(list[i], i, i == _selected),
              ],
            ),
          ),
          Container(
            padding: EdgeInsets.fromLTRB(
                rpx(32), rpx(16), rpx(32), bottom + rpx(16)),
            decoration: const BoxDecoration(
              color: BrandColors.bgCard,
              border: Border(top: BorderSide(color: BrandColors.border)),
            ),
            child: PrimaryButton(
              label: _submitting ? '处理中…' : '分析所选段',
              loading: _submitting,
              height: rpx(88),
              onTap: () => _confirm(pending),
            ),
          ),
        ],
      ),
    );
  }

  Widget _item(SwingCandidate item, int index, bool active) {
    return GestureDetector(
      onTap: () => setState(() => _selected = index),
      child: Container(
        margin: EdgeInsets.only(bottom: rpx(16)),
        padding: EdgeInsets.all(rpx(20)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(
            color: active ? BrandColors.primary : BrandColors.border,
            width: active ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(Radii.md),
              child: (item.previewFrameUrl?.isNotEmpty ?? false)
                  ? CachedNetworkImage(
                      imageUrl: item.previewFrameUrl!,
                      width: rpx(120),
                      height: rpx(120),
                      fit: BoxFit.cover,
                      errorWidget: (_, _, _) => _thumbPlaceholder(index),
                    )
                  : _thumbPlaceholder(index),
            ),
            SizedBox(width: rpx(20)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('第 ${index + 1} 段',
                          style: TextStyle(
                              fontSize: rpx(30),
                              fontWeight: FontWeight.w700,
                              color: BrandColors.textPrimary)),
                      SizedBox(width: rpx(12)),
                      Container(
                        padding: EdgeInsets.symmetric(
                            horizontal: rpx(14), vertical: rpx(4)),
                        decoration: BoxDecoration(
                          color: item.isPractice
                              ? BrandColors.amberBg
                              : BrandColors.accentMintDim,
                          borderRadius: BorderRadius.circular(rpx(20)),
                        ),
                        child: Text(item.isPractice ? '试挥' : '正式',
                            style: TextStyle(
                                fontSize: rpx(22),
                                fontWeight: FontWeight.w600,
                                color: item.isPractice
                                    ? BrandColors.amber
                                    : BrandColors.success)),
                      ),
                    ],
                  ),
                  SizedBox(height: rpx(8)),
                  Text(
                    '${_fmtTime(item.startTimeSec)} – ${_fmtTime(item.endTimeSec)}',
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.textSecondary),
                  ),
                ],
              ),
            ),
            if (active)
              Icon(Icons.check_circle,
                  color: BrandColors.primary, size: rpx(40)),
          ],
        ),
      ),
    );
  }

  Widget _thumbPlaceholder(int index) => Container(
        width: rpx(120),
        height: rpx(120),
        alignment: Alignment.center,
        color: BrandColors.primaryTint,
        child: Text('${index + 1}',
            style: TextStyle(
                fontSize: rpx(40),
                fontWeight: FontWeight.w700,
                color: BrandColors.primary)),
      );
}
