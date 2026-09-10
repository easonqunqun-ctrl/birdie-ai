import 'package:flutter/material.dart';

import '../../../l10n/l10n.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 帮助中心：常见问题。对照 client/src/pages/help。
class HelpPage extends StatelessWidget {
  const HelpPage({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final faqs = <(String, String)>[
      (l10n.faqShootQ, l10n.faqShootA),
      (l10n.faqHowLongQ, l10n.faqHowLongA),
      (l10n.faqQuotaQ, l10n.faqQuotaA),
      (l10n.faqCoachQ, l10n.faqCoachA),
      (l10n.faqDataQ, l10n.faqDataA),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l10n.helpCenter)),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          for (final f in faqs)
            Container(
              margin: EdgeInsets.only(bottom: rpx(20)),
              decoration: BoxDecoration(
                color: BrandColors.bgCard,
                borderRadius: BorderRadius.circular(Radii.lg),
                border: Border.all(color: BrandColors.border),
              ),
              child: Theme(
                data: Theme.of(context)
                    .copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: Text(f.$1,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.textPrimary)),
                  childrenPadding: EdgeInsets.fromLTRB(
                      rpx(32), 0, rpx(32), rpx(28)),
                  children: [
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(f.$2,
                          style: TextStyle(
                              fontSize: rpx(28),
                              height: 1.6,
                              color: BrandColors.textSecondary)),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
