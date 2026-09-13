import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../l10n/l10n.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';

/// 会员中心：展示权益对比；iOS 本版不提供 App 内付费入口（Guideline 3.1.1）。
/// 苹果 IAP 上线前，App 内仅可使用免费额度；勿引导微信/小程序支付。
class MembershipPage extends StatefulWidget {
  const MembershipPage({super.key});

  @override
  State<MembershipPage> createState() => _MembershipPageState();
}

class _MembershipPageState extends State<MembershipPage> {

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final user = context.watch<AuthController>().user;
    final isMember = user?.isMember == true;
    final typeLabel = switch (user?.membershipType) {
      'yearly' || 'annual' => l10n.memberYearly,
      'monthly' => l10n.memberMonthly,
      _ => l10n.memberGeneric,
    };
    final benefits = <(String, String, String)>[
      (l10n.benefitSwing, l10n.tierLimitedMonth, l10n.tierUnlimited),
      (l10n.benefitCoach, l10n.tierLimitedDay, l10n.tierUnlimited),
      (l10n.benefitPlan, l10n.tierViewOnly, l10n.tierFullPlan),
      (l10n.benefitCurve, l10n.tierBasic, l10n.tierFullHistory),
      (l10n.benefitCompare, l10n.tierBasic, l10n.tierSideBySide),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l10n.membershipCenter)),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
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
                Text(
                    isMember
                        ? '👑 ${l10n.memberRemainingDays(typeLabel, user?.membershipDaysRemaining ?? 0)}'
                        : '🎯 ${l10n.freeUser}',
                    style: TextStyle(
                        fontSize: rpx(36),
                        fontWeight: FontWeight.w800,
                        color: Colors.white)),
                SizedBox(height: rpx(12)),
                Text(
                  isMember
                      ? l10n.memberThanks
                      : (user?.promoFree?.active == true
                          ? (user!.promoFree!.message ??
                              (context.l10n.localeName
                                      .toLowerCase()
                                      .startsWith('en')
                                  ? 'New-user trial: unlimited for 3 months from sign-up, then 3 analyses per month.'
                                  : '注册起 3 个月不限次；到期后每月 3 次，再多用请开通会员'))
                          : l10n.membershipFreeHint),
                  style: TextStyle(fontSize: rpx(28), color: Colors.white70),
                ),
              ],
            ),
          ),
          SizedBox(height: rpx(32)),
          _benefitTable(benefits),
          if (!isMember) ...[
            SizedBox(height: rpx(32)),
            Container(
              padding: EdgeInsets.all(rpx(28)),
              decoration: BoxDecoration(
                color: BrandColors.bgCard,
                borderRadius: BorderRadius.circular(Radii.md),
                border: Border.all(color: BrandColors.border),
              ),
              child: Text(
                l10n.membershipNoIap,
                style: TextStyle(
                    fontSize: rpx(26),
                    height: 1.5,
                    color: BrandColors.textSecondary),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _benefitTable(List<(String, String, String)> benefits) {
    return Container(
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.all(rpx(24)),
            child: Row(
              children: [
                Expanded(
                    child: Text(context.l10n.colBenefit,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary))),
                SizedBox(
                    width: rpx(140),
                    child: Text(context.l10n.colFree,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary))),
                SizedBox(
                    width: rpx(160),
                    child: Text(context.l10n.memberGeneric,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.goldDark))),
              ],
            ),
          ),
          for (final b in benefits)
            Padding(
              padding: EdgeInsets.fromLTRB(rpx(24), 0, rpx(24), rpx(20)),
              child: Row(
                children: [
                  Expanded(
                      child: Text(b.$1,
                          style: TextStyle(
                              fontSize: rpx(26),
                              color: BrandColors.textPrimary))),
                  SizedBox(
                      width: rpx(140),
                      child: Text(b.$2,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(24),
                              color: BrandColors.textTertiary))),
                  SizedBox(
                      width: rpx(160),
                      child: Text(b.$3,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(24),
                              fontWeight: FontWeight.w600,
                              color: BrandColors.primary))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
