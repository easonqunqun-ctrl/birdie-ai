import 'package:flutter/material.dart';

import '../../../core/app_info.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/brand_logo.dart';
import '../../legal/pages/legal_page.dart';

/// 关于领翼golf：品牌信息 + 版本 + 主体/备案 + 协议入口。
class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('关于')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          SizedBox(height: rpx(48)),
          const Center(child: BrandLogo(size: 96)),
          SizedBox(height: rpx(24)),
          Center(
            child: Text('领翼golf',
                style: TextStyle(
                    fontSize: rpx(40),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.primary)),
          ),
          SizedBox(height: rpx(12)),
          Center(
            child: Text(kBrandSubtitle,
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
          ),
          SizedBox(height: rpx(48)),
          _metaRow('版本', 'v$kClientVersion'),
          Divider(height: 1, color: BrandColors.divider),
          _metaRow('主体', kCompanyName),
          Divider(height: 1, color: BrandColors.divider),
          _metaRow('ICP 备案', kIcpNumber),
          SizedBox(height: rpx(48)),
          _row(context, '用户服务协议', LegalKind.terms),
          Divider(height: 1, color: BrandColors.divider),
          _row(context, '隐私政策', LegalKind.privacy),
          SizedBox(height: rpx(64)),
          Center(
            child: Text(kCopyright,
                style: TextStyle(
                    fontSize: rpx(22), color: BrandColors.textTertiary)),
          ),
        ],
      ),
    );
  }

  Widget _metaRow(String label, String value) => Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(30)),
        child: Row(
          children: [
            Expanded(
              child: Text(label,
                  style: TextStyle(
                      fontSize: rpx(30), color: BrandColors.textPrimary)),
            ),
            Text(value,
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
          ],
        ),
      );

  Widget _row(BuildContext context, String label, LegalKind kind) =>
      GestureDetector(
        onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => LegalPage(kind: kind))),
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: rpx(30)),
          child: Row(
            children: [
              Expanded(
                child: Text(label,
                    style: TextStyle(
                        fontSize: rpx(30), color: BrandColors.textPrimary)),
              ),
              const Icon(Icons.chevron_right, color: BrandColors.textTertiary),
            ],
          ),
        ),
      );
}
