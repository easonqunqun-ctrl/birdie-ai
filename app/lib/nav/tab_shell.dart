import 'package:flutter/material.dart';

import '../theme/brand_colors.dart';
import '../theme/dimens.dart';
import '../features/home/pages/home_page.dart';
import '../features/coach/pages/coach_page.dart';
import '../features/training/pages/training_page.dart';
import '../features/profile/pages/profile_page.dart';
import '../l10n/l10n.dart';

/// 底部自定义 TabBar：对齐小程序 custom-tab-bar（56rpx 图标 / 28rpx 文案）。
///
/// 懒加载各 Tab：登录进首页时不再同时拉起教练/训练的网络请求（IndexedStack 会四页一起 init）。
class TabShell extends StatefulWidget {
  const TabShell({super.key});

  @override
  State<TabShell> createState() => _TabShellState();
}

class _TabShellState extends State<TabShell> {
  int _index = 0;
  final Map<int, Widget> _pages = {};

  static const _icons = [
    ('assets/tab/home.png', 'assets/tab/home_active.png'),
    ('assets/tab/coach.png', 'assets/tab/coach_active.png'),
    ('assets/tab/training.png', 'assets/tab/training_active.png'),
    ('assets/tab/profile.png', 'assets/tab/profile_active.png'),
  ];

  @override
  void initState() {
    super.initState();
    _ensurePage(0);
  }

  void _ensurePage(int i) {
    _pages.putIfAbsent(i, () {
      switch (i) {
        case 1:
          return const CoachPage();
        case 2:
          return const TrainingPage();
        case 3:
          return const ProfilePage();
        case 0:
        default:
          return const HomePage();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final labels = [l10n.tabHome, l10n.tabCoach, l10n.tabTraining, l10n.tabProfile];
    final bottom = MediaQuery.of(context).padding.bottom;
    // 已访问过的 Tab 用 Stack+Offstage 保活；未访问的不创建，避免冷启动四路 API。
    final visited = _pages.keys.toList()..sort();
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: Stack(
        children: [
          for (final i in visited)
            Offstage(
              offstage: i != _index,
              child: TickerMode(
                enabled: i == _index,
                child: _pages[i]!,
              ),
            ),
        ],
      ),
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
            for (var i = 0; i < labels.length; i++)
              Expanded(child: _tabItem(i, labels[i])),
          ],
        ),
      ),
    );
  }

  Widget _tabItem(int i, String label) {
    final active = _index == i;
    final icons = _icons[i];
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () {
        if (_index == i) return;
        setState(() {
          _ensurePage(i);
          _index = i;
        });
      },
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(height: rpx(10)),
          Image.asset(
            active ? icons.$2 : icons.$1,
            width: rpx(56),
            height: rpx(56),
          ),
          SizedBox(height: rpx(4)),
          Text(
            label,
            style: TextStyle(
              fontSize: rpx(22),
              fontWeight: active ? FontWeight.w700 : FontWeight.w500,
              color: active ? BrandColors.primary : BrandColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}
