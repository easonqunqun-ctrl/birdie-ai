import 'package:flutter/material.dart';

/// 四色体系（源：client/src/app.scss §7.2 视觉规范）。
/// 业务页一律引用这里的常量，禁止散落硬编码 HEX。
class BrandColors {
  BrandColors._();

  // 品牌主色（靛蓝）
  static const primary = Color(0xFF1A237E);
  static const primaryDark = Color(0xFF121A5C);
  static const primarySoft = Color(0xFF0D3B8E);
  static const primaryTint = Color(0xFFE8EBF8);
  static const onPrimary = Color(0xFFFFFFFF);
  static const onPrimaryMuted = Color(0xFFC5CCF5);

  // 点缀绿（成长 / 完成 / 上行）
  static const accentMint = Color(0xFF00D084);
  static const accentMintDim = Color(0xFFE8F5EE);

  // 强调金（会员 / 成就 / 关键数据，小面积点缀）
  static const gold = Color(0xFFC9A227);
  static const goldDark = Color(0xFF7A5F10);
  static const goldSoft = Color(0xFFFFF4D6);

  // 语义色
  static const success = Color(0xFF00A066);
  static const warning = Color(0xFFF4A923);
  static const amber = Color(0xFFC47A00);
  static const amberBg = Color(0xFFFFF4E0);
  static const error = Color(0xFFEF4444);
  static const info = Color(0xFF3B82F6);

  // 文字
  static const textPrimary = Color(0xFF1F2937);
  static const textSecondary = Color(0xFF6B7280);
  static const textTertiary = Color(0xFF9CA3AF);
  static const textMuted = Color(0xFF888888);

  // 背景 / 描边
  static const bgPage = Color(0xFFF4F6FC);
  static const bgCard = Color(0xFFFFFFFF);
  static const bgSubtle = Color(0xFFF0F2F5);
  static const border = Color(0xFFEAEBEF);
  static const borderMuted = Color(0xFFE0E3F0);
  static const divider = Color(0xFFEAEBEF);
  static const contextBorder = Color(0xFFC8CEEC);

  // 渐变
  static const gradientHero = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primarySoft, Color(0xFF094A30)],
    stops: [0.0, 0.52, 1.0],
  );
  static const gradientStreak = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF1A237E), Color(0xFF0A3A6E)],
  );
  /// 登录 / 合规页氛围：对照 login/consent SCSS `primary-tint → bg-card`。
  static const gradientAuthAtmosphere = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [primaryTint, bgCard],
    stops: [0.0, 0.55],
  );
}
