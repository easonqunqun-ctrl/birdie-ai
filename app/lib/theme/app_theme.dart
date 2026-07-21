import 'package:flutter/material.dart';
import 'brand_colors.dart';
import 'dimens.dart';

/// 全局 ThemeData：把四色体系接进 Material，保证默认组件也走品牌色。
class AppTheme {
  AppTheme._();

  static ThemeData get light {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: BrandColors.bgPage,
      fontFamily: null,
      colorScheme: const ColorScheme.light(
        primary: BrandColors.primary,
        onPrimary: BrandColors.onPrimary,
        secondary: BrandColors.accentMint,
        error: BrandColors.error,
        surface: BrandColors.bgCard,
        onSurface: BrandColors.textPrimary,
      ),
    );

    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: BrandColors.bgPage,
        foregroundColor: BrandColors.textPrimary,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: BrandColors.textPrimary,
          fontSize: 17,
          fontWeight: FontWeight.w600,
        ),
      ),
      textTheme: base.textTheme.apply(
        bodyColor: BrandColors.textPrimary,
        displayColor: BrandColors.textPrimary,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: BrandColors.primary,
          foregroundColor: BrandColors.onPrimary,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(Radii.md),
          ),
        ),
      ),
    );
  }
}
