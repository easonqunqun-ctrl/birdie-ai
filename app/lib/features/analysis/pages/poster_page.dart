import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/analysis_options.dart';
import '../../../core/env.dart';
import '../../../core/swing_constants.dart';
import '../../../data/models/analysis.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 成绩海报（简化版）：对照 weapp poster，App 先做可分享卡片 + 系统分享。
class PosterPage extends StatelessWidget {
  const PosterPage({super.key, required this.report});
  final AnalysisReport report;

  String get _shareUrl => Env.publicReportUrl(report.id);

  Future<void> _share(BuildContext context) async {
    final score = report.overallScore?.round() ?? '—';
    final club = clubTypeLabels[report.clubType] ?? report.clubType;
    final text = '我在领翼golf 打出了 $score 分（$club）\n$_shareUrl';
    await Share.share(text, subject: '领翼golf 挥杆成绩');
  }

  Future<void> _copyLink(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: _shareUrl));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('已复制分享链接')));
  }

  @override
  Widget build(BuildContext context) {
    final score = report.overallScore?.round() ?? '—';
    final level = report.scoreLevel ?? scoreLevelFromScore(report.overallScore);
    final meta = level != null ? kScoreLevelMeta[level] : null;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('成绩海报')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          Container(
            width: double.infinity,
            padding: EdgeInsets.all(rpx(40)),
            decoration: BoxDecoration(
              gradient: BrandColors.gradientHero,
              borderRadius: BorderRadius.circular(Radii.lg),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('领翼golf',
                    style: TextStyle(
                        fontSize: rpx(28),
                        fontWeight: FontWeight.w700,
                        color: BrandColors.onPrimaryMuted)),
                SizedBox(height: rpx(24)),
                Text('$score',
                    style: TextStyle(
                        fontSize: rpx(120),
                        height: 1,
                        fontWeight: FontWeight.w900,
                        color: BrandColors.onPrimary)),
                Text('综合分',
                    style: TextStyle(
                        fontSize: rpx(28), color: BrandColors.onPrimaryMuted)),
                SizedBox(height: rpx(20)),
                Text(
                    '${meta?.emoji ?? '⛳️'} ${meta?.label ?? '挥杆分析'} · ${clubTypeLabels[report.clubType] ?? report.clubType}',
                    style: TextStyle(
                        fontSize: rpx(30),
                        fontWeight: FontWeight.w600,
                        color: BrandColors.onPrimary)),
              ],
            ),
          ),
          SizedBox(height: rpx(32)),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => _share(context),
              icon: const Icon(Icons.ios_share),
              label: const Text('分享成绩'),
            ),
          ),
          SizedBox(height: rpx(16)),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () => _copyLink(context),
              child: const Text('复制报告链接'),
            ),
          ),
          SizedBox(height: rpx(16)),
          Text(
              '分享链接指向公开脱敏报告；完整视频与训练建议仅本人可见。',
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.textTertiary)),
        ],
      ),
    );
  }
}
