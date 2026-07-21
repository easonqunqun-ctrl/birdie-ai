import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';

/// 会员中心：对照 client/src/pages/profile/membership。权益对比 + 状态。
/// 支付接入在后续里程碑（需微信支付资质），当前 CTA 占位。
class MembershipPage extends StatelessWidget {
  const MembershipPage({super.key});

  static const _benefits = <(String, String, String)>[
    ('挥杆视频分析', '每月 3 次', '无限次'),
    ('AI 教练对话', '每天 5 轮', '无限次'),
    ('本周训练计划', '仅查看', '完整个性化'),
    ('进步曲线', '锁定', '完整历史与折线'),
    ('历史报告对比', '基础', '并排对比 + 晒进步'),
  ];

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthController>().user;
    final isMember = user?.isMember == true;
    final typeLabel = switch (user?.membershipType) {
      'annual' => '年度会员',
      'monthly' => '月度会员',
      _ => '会员',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('会员中心')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          Container(
            padding: EdgeInsets.all(rpx(24)),
            decoration: BoxDecoration(
              color: BrandColors.primaryTint,
              borderRadius: BorderRadius.circular(Radii.md),
            ),
            child: Text('内测阶段 · 付费功能未开放，所有用户均按「无限」配额体验',
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.primaryDark)),
          ),
          SizedBox(height: rpx(24)),
          Container(
            padding: EdgeInsets.all(rpx(40)),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFC9A227), Color(0xFF7A5F10)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(Radii.lg),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(isMember ? '👑' : '🎯',
                        style: TextStyle(fontSize: rpx(44))),
                    SizedBox(width: rpx(12)),
                    Text(isMember ? '$typeLabel · 还剩 ${user?.membershipDaysRemaining ?? 0} 天' : '免费用户',
                        style: TextStyle(
                            fontSize: rpx(38),
                            fontWeight: FontWeight.w800,
                            color: Colors.white)),
                  ],
                ),
                SizedBox(height: rpx(16)),
                Text(
                  isMember ? '感谢支持，尽情享受全部会员权益' : '解锁无限次挥杆分析与 AI 教练对话',
                  style: TextStyle(fontSize: rpx(28), color: Colors.white70),
                ),
              ],
            ),
          ),
          SizedBox(height: rpx(32)),
          _benefitTable(),
          SizedBox(height: rpx(48)),
          if (!isMember)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('支付功能即将上线')),
                ),
                style: ElevatedButton.styleFrom(
                    padding: EdgeInsets.symmetric(vertical: rpx(24))),
                child: const Text('立即开通'),
              ),
            ),
        ],
      ),
    );
  }

  Widget _benefitTable() {
    return Container(
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          _tableRow('功能', '免费', '会员', header: true),
          for (final b in _benefits)
            _tableRow(b.$1, b.$2, b.$3),
        ],
      ),
    );
  }

  Widget _tableRow(String a, String b, String c, {bool header = false}) {
    final style = TextStyle(
      fontSize: rpx(26),
      fontWeight: header ? FontWeight.w700 : FontWeight.w400,
      color: header ? BrandColors.textPrimary : BrandColors.textSecondary,
    );
    final memberStyle = TextStyle(
      fontSize: rpx(26),
      fontWeight: FontWeight.w700,
      color: header ? BrandColors.textPrimary : BrandColors.goldDark,
    );
    return Container(
      padding: EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(24)),
      decoration: BoxDecoration(
        border: header
            ? const Border(
                bottom: BorderSide(color: BrandColors.border, width: 1))
            : const Border(
                bottom: BorderSide(color: BrandColors.divider, width: 0.5)),
      ),
      child: Row(
        children: [
          Expanded(flex: 4, child: Text(a, style: style)),
          Expanded(
              flex: 3,
              child: Text(b, textAlign: TextAlign.center, style: style)),
          Expanded(
              flex: 3,
              child:
                  Text(c, textAlign: TextAlign.center, style: memberStyle)),
        ],
      ),
    );
  }
}
