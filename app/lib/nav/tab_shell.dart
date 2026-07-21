import 'package:flutter/material.dart';

import '../theme/brand_colors.dart';
import '../features/home/pages/home_page.dart';
import '../features/coach/pages/coach_page.dart';
import '../features/training/pages/training_page.dart';
import '../features/profile/pages/profile_page.dart';

/// 底部 TabBar 主壳：首页 / AI 教练 / 训练 / 我的（对齐小程序 tabBar）。
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        type: BottomNavigationBarType.fixed,
        backgroundColor: BrandColors.bgCard,
        selectedItemColor: BrandColors.primary,
        unselectedItemColor: BrandColors.textTertiary,
        selectedFontSize: 12,
        unselectedFontSize: 12,
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined),
              activeIcon: Icon(Icons.home),
              label: '首页'),
          BottomNavigationBarItem(
              icon: Icon(Icons.chat_bubble_outline),
              activeIcon: Icon(Icons.chat_bubble),
              label: 'AI 教练'),
          BottomNavigationBarItem(
              icon: Icon(Icons.fitness_center_outlined),
              activeIcon: Icon(Icons.fitness_center),
              label: '训练'),
          BottomNavigationBarItem(
              icon: Icon(Icons.person_outline),
              activeIcon: Icon(Icons.person),
              label: '我的'),
        ],
      ),
    );
  }
}
