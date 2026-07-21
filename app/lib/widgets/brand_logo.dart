import 'package:flutter/material.dart';
import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

/// 品牌 LOGO（assets/brand/logo.png，源同小程序 BRAND_LOGO）。
class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, this.size = 100});
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.xl),
        border: Border.all(color: const Color(0x141A237E)),
        boxShadow: [
          BoxShadow(
            color: BrandColors.primary.withValues(alpha: 0.18),
            offset: Offset(0, rpx(12)),
            blurRadius: rpx(14),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Image.asset('assets/brand/logo.png', fit: BoxFit.contain),
    );
  }
}
