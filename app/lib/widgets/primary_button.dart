import 'package:flutter/material.dart';
import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

/// 主 CTA 按钮：靛蓝填充胶囊，对齐小程序 .btn。
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onTap,
    this.loading = false,
    this.disabled = false,
    this.height = 48,
  });

  final String label;
  final VoidCallback? onTap;
  final bool loading;
  final bool disabled;
  final double height;

  @override
  Widget build(BuildContext context) {
    final inactive = disabled || loading;
    return Opacity(
      opacity: inactive ? 0.6 : 1,
      child: GestureDetector(
        onTap: inactive ? null : onTap,
        child: Container(
          height: height,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: BrandColors.primary,
            borderRadius: BorderRadius.circular(Radii.md),
          ),
          child: loading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor:
                        AlwaysStoppedAnimation<Color>(BrandColors.onPrimary),
                  ),
                )
              : Text(
                  label,
                  style: TextStyle(
                    color: BrandColors.onPrimary,
                    fontSize: rpx(34),
                    fontWeight: FontWeight.w600,
                  ),
                ),
        ),
      ),
    );
  }
}
