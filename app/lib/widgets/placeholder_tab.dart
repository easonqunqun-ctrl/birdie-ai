import 'package:flutter/material.dart';
import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

/// 里程碑占位页：M0 用来占位未复刻的 Tab / 子页。
class PlaceholderTab extends StatelessWidget {
  const PlaceholderTab({
    super.key,
    required this.title,
    required this.milestone,
    this.icon = Icons.construction,
  });

  final String title;
  final String milestone;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: BrandColors.bgPage,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: rpx(96), color: BrandColors.textTertiary),
            SizedBox(height: rpx(24)),
            Text(title,
                style: TextStyle(
                    fontSize: rpx(40),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            SizedBox(height: rpx(12)),
            Text('将在 $milestone 复刻',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
          ],
        ),
      ),
    );
  }
}
