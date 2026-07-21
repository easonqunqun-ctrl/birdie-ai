import 'package:flutter/widgets.dart';

/// 圆角阶梯（对齐 app.scss --radius-*）
class Radii {
  Radii._();
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
}

/// rpx → 逻辑像素：小程序 750 设计宽 → 设备实际宽等比缩放。
/// 与 client/src/adapters/rnScale.ts 同一思路，保证与小程序视觉同比例。
double _cachedWidth = 0;

double rpx(num n) {
  if (_cachedWidth <= 0) {
    final view = WidgetsBinding.instance.platformDispatcher.views.first;
    final w = view.physicalSize.width / view.devicePixelRatio;
    _cachedWidth = w > 0 ? w : 390.0;
  }
  return n * _cachedWidth / 750.0;
}
