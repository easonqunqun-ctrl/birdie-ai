import 'package:flutter/material.dart';
import '../theme/dimens.dart';

/// 品牌 LOGO：深色版（黑底 Birdie AI），对齐小程序 BRAND_LOGO。
class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, this.size = 100});
  final double size;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(Radii.xl),
      child: Image.asset(
        'assets/brand/logo.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
      ),
    );
  }
}
