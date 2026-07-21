import 'package:flutter/material.dart';

import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/placeholder_tab.dart';
import '../../help/pages/help_page.dart';
import 'courses_page.dart';
import 'meetup_page.dart';
import 'pros_page.dart';

/// 发现：长尾内容入口（课程 / 高手对比 / 约球 / 帮助）。
class DiscoverPage extends StatelessWidget {
  const DiscoverPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('发现')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          _card(context, Icons.school, '课程学习', '系统化提升，阶段进阶',
              const CoursesPage()),
          _card(context, Icons.emoji_events, '高手对比', '对照职业球手挥杆',
              const ProsPage()),
          _card(context, Icons.groups, '约球 / 挑战赛', '和球友一起打卡比拼',
              const MeetupPage()),
          _card(context, Icons.help_outline, '帮助中心', '常见问题与使用指南',
              const HelpPage()),
          SizedBox(height: rpx(24)),
          Text('更多功能陆续开放',
              style: TextStyle(
                  fontSize: rpx(26), color: BrandColors.textTertiary)),
          SizedBox(height: rpx(16)),
          _card(context, Icons.compare, '挥杆对比', '前后两次挥杆对照',
              const PlaceholderTab(title: '挥杆对比', milestone: '后续版本')),
          _card(context, Icons.image, '成绩海报', '生成分享海报',
              const PlaceholderTab(title: '成绩海报', milestone: '后续版本')),
          _card(context, Icons.sports, '教练工作台', '教练端学员管理',
              const PlaceholderTab(title: '教练工作台', milestone: '后续版本')),
        ],
      ),
    );
  }

  Widget _card(BuildContext context, IconData icon, String title, String sub,
          Widget page) =>
      GestureDetector(
        onTap: () => Navigator.of(context)
            .push(MaterialPageRoute(builder: (_) => page)),
        child: Container(
          margin: EdgeInsets.only(bottom: rpx(20)),
          padding: EdgeInsets.all(rpx(32)),
          decoration: BoxDecoration(
            color: BrandColors.bgCard,
            borderRadius: BorderRadius.circular(Radii.lg),
            border: Border.all(color: BrandColors.border),
          ),
          child: Row(
            children: [
              Container(
                width: rpx(88),
                height: rpx(88),
                decoration: BoxDecoration(
                  color: BrandColors.primaryTint,
                  borderRadius: BorderRadius.circular(Radii.md),
                ),
                child: Icon(icon, color: BrandColors.primary, size: 30),
              ),
              SizedBox(width: rpx(24)),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: TextStyle(
                            fontSize: rpx(32),
                            fontWeight: FontWeight.w700,
                            color: BrandColors.textPrimary)),
                    SizedBox(height: rpx(8)),
                    Text(sub,
                        style: TextStyle(
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: BrandColors.textTertiary),
            ],
          ),
        ),
      );
}
