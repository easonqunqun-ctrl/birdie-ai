import 'package:flutter/material.dart';

import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 帮助中心：常见问题。对照 client/src/pages/help。
class HelpPage extends StatelessWidget {
  const HelpPage({super.key});

  static const _faqs = <(String, String)>[
    ('如何拍摄一段合格的挥杆视频？',
        '建议在光线充足的场地，手机横屏或竖屏固定，完整拍下从预备到收杆的动作；'
            '正面（Face-On）或侧面（Down-the-Line）机位皆可，时长 2-30 秒。'),
    ('分析需要多久？',
        '视频上传后，AI 通常在 30 秒内完成分析并生成报告，弱网时可能稍长。'),
    ('分析次数用完了怎么办？',
        '免费额度每月刷新；开通会员可享无限次挥杆分析与 AI 教练对话。'),
    ('AI 教练能回答哪些问题？',
        '挥杆技术、训练计划、规则疑问、装备选择等高尔夫相关问题都可以问。'),
    ('我的数据安全吗？',
        '所有数据存储在中国境内服务器，加密传输与存储；你可随时在「我的」删除或注销账号。'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('帮助中心')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          for (final f in _faqs)
            Container(
              margin: EdgeInsets.only(bottom: rpx(20)),
              decoration: BoxDecoration(
                color: BrandColors.bgCard,
                borderRadius: BorderRadius.circular(Radii.lg),
                border: Border.all(color: BrandColors.border),
              ),
              child: Theme(
                data: Theme.of(context)
                    .copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: Text(f.$1,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.textPrimary)),
                  childrenPadding: EdgeInsets.fromLTRB(
                      rpx(32), 0, rpx(32), rpx(28)),
                  children: [
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(f.$2,
                          style: TextStyle(
                              fontSize: rpx(28),
                              height: 1.6,
                              color: BrandColors.textSecondary)),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
