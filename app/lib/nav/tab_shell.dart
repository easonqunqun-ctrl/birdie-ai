import 'package:flutter/material.dart';

import '../theme/brand_colors.dart';
import '../theme/dimens.dart';
import '../features/home/pages/home_page.dart';
import '../features/coach/pages/coach_page.dart';
import '../features/training/pages/training_page.dart';
import '../features/profile/pages/profile_page.dart';

/// 底部自定义 TabBar：对齐小程序 custom-tab-bar（56rpx 图标 / 28rpx 文案）。
class TabShell extends StatefulWidget {
  const TabShell({super.key});

  @override
  State<TabShell> createState() => _TabShellState();
}

class _TabShellState extends State<TabShell> {
  int _index = 0;

  static const _pages = [
    HomePage(),
    CoachPage(),
    TrainingPage(),
    ProfilePage(),
  ];

  static const _labels = ['首页', 'AI 教练', '训练', '我的'];
  static const _icons = [
    ('assets/tab/home.png', 'assets/tab/home_active.png'),
    ('assets/tab/coach.png', 'assets/tab/coach_active.png'),
    ('assets/tab/training.png', 'assets/tab/training_active.png'),
    ('assets/tab/profile.png', 'assets/tab/profile_active.png'),
  ];

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).padding.bottom;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          border: const Border(
            top: BorderSide(color: Color(0x141A237E), width: 0.5),
          ),
          boxShadow: [
            BoxShadow(
              color: BrandColors.primary.withValues(alpha: 0.06),
              blurRadius: rpx(16),
              offset: Offset(0, -rpx(4)),
            ),
          ],
        ),
        padding: EdgeInsets.only(bottom: bottom),
        height: rpx(112) + bottom,
        child: Row(
          children: [
            for (var i = 0; i < _labels.length; i++)
              Expanded(child: _tabItem(i)),
          ],
        ),
      ),
    );
  }

  Widget _tabItem(int i) {
    final active = _index == i;
    final icons = _icons[i];
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => setState(() => _index = i),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(height: rpx(10)),
          Image.asset(
            active ? icons.$2 : icons.$1,
            width: rpx(56),
            height: rpx(56),
            fit: BoxFit.contain,
          ),
          SizedBox(height: rpx(6)),
          Text(
            _labels[i],
            style: TextStyle(
              fontSize: rpx(28),
              height: 1.2,
              fontWeight: active ? FontWeight.w600 : FontWeight.w500,
              color: active ? BrandColors.primary : BrandColors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}
