import 'package:flutter/material.dart';

import '../core/trust_label.dart';
import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

/// 报告可信度色块：对照 client TrustBadge。
class TrustBadge extends StatelessWidget {
  const TrustBadge({
    super.key,
    required this.confidence,
    this.onRetake,
  });

  final num? confidence;
  final VoidCallback? onRetake;

  @override
  Widget build(BuildContext context) {
    final tier = resolveTrustTier(confidence);
    final copy = trustTierCopy(tier);
    final pct = '${((confidence ?? 1.0) * 100).round()}%';
    final (bg, border, fg) = switch (tier) {
      TrustTier.high => (
          BrandColors.accentMintDim,
          BrandColors.accentMint.withValues(alpha: 0.45),
          BrandColors.success,
        ),
      TrustTier.medium => (
          BrandColors.goldSoft,
          BrandColors.gold.withValues(alpha: 0.45),
          BrandColors.goldDark,
        ),
      TrustTier.low => (
          BrandColors.amberBg,
          BrandColors.warning.withValues(alpha: 0.45),
          BrandColors.amber,
        ),
    };

    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(28)),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(Radii.md),
        border: Border.all(color: border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(copy.title,
                    style: TextStyle(
                        fontSize: rpx(30),
                        fontWeight: FontWeight.w700,
                        color: fg)),
              ),
              Text(pct,
                  style: TextStyle(
                      fontSize: rpx(28),
                      fontWeight: FontWeight.w700,
                      color: fg)),
            ],
          ),
          SizedBox(height: rpx(10)),
          Text(copy.hint,
              style: TextStyle(
                  fontSize: rpx(24),
                  height: 1.45,
                  color: BrandColors.textSecondary)),
          if (tier == TrustTier.low && onRetake != null) ...[
            SizedBox(height: rpx(20)),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: onRetake,
                style: OutlinedButton.styleFrom(
                  foregroundColor: fg,
                  side: BorderSide(color: fg),
                ),
                child: const Text('立即重拍一段'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
