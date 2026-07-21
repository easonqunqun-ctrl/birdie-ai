import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/app_info.dart';
import '../../../core/storage.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';
import '../../legal/pages/legal_page.dart';
import 'about_page.dart';
import 'account_deletion_page.dart';

/// 设置：对照 client/src/pages/profile/settings。体验工具 + 法律 + 账号。
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          _sectionTitle('体验'),
          _group([
            _row(context, '重新查看拍摄指南', onTap: () => _replayGuide(context)),
            _divider(),
            _row(context, '清除本地缓存', onTap: () => _clearCache(context)),
          ]),
          SizedBox(height: rpx(32)),
          _sectionTitle('法律与协议'),
          _group([
            _row(context, '用户服务协议',
                onTap: () => _go(context, const LegalPage(kind: LegalKind.terms))),
            _divider(),
            _row(context, '隐私政策',
                onTap: () =>
                    _go(context, const LegalPage(kind: LegalKind.privacy))),
            _divider(),
            _row(context, '关于领翼golf',
                trailing: 'v$kClientVersion',
                onTap: () => _go(context, const AboutPage())),
          ]),
          SizedBox(height: rpx(32)),
          _group([
            _row(context, '注销账号',
                onTap: () => _go(context, const AccountDeletionPage())),
          ]),
          SizedBox(height: rpx(32)),
          _logoutButton(context),
        ],
      ),
    );
  }

  void _go(BuildContext context, Widget page) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));

  Future<void> _replayGuide(BuildContext context) async {
    await AppStorage.instance.clearAnalysisGuideSeen();
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已重置，下次分析会再次显示拍摄指南')));
  }

  Future<void> _clearCache(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('清除本地缓存'),
        content: const Text('将清除本地登录态与设置缓存，需要重新登录。确认继续？'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, true), child: const Text('清除')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    await AppStorage.instance.clearAnalysisGuideSeen();
    if (context.mounted) await context.read<AuthController>().logout();
  }

  Widget _logoutButton(BuildContext context) => GestureDetector(
        onTap: () async {
          final ok = await showDialog<bool>(
            context: context,
            builder: (c) => AlertDialog(
              title: const Text('提示'),
              content: const Text('确认退出登录？'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(c, false),
                    child: const Text('取消')),
                TextButton(
                    onPressed: () => Navigator.pop(c, true),
                    child: const Text('退出登录')),
              ],
            ),
          );
          if (ok == true && context.mounted) {
            await context.read<AuthController>().logout();
          }
        },
        child: Container(
          height: rpx(96),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: BrandColors.bgCard,
            borderRadius: BorderRadius.circular(Radii.md),
            border: Border.all(color: BrandColors.border),
          ),
          child: Text('退出登录',
              style: TextStyle(fontSize: rpx(32), color: BrandColors.error)),
        ),
      );

  Widget _sectionTitle(String t) => Padding(
        padding: EdgeInsets.only(left: rpx(8), bottom: rpx(16)),
        child: Text(t,
            style: TextStyle(
                fontSize: rpx(26), color: BrandColors.textTertiary)),
      );

  Widget _group(List<Widget> rows) => Container(
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Column(children: rows),
      );

  Widget _divider() =>
      Divider(height: 1, color: BrandColors.divider, indent: rpx(32));

  Widget _row(BuildContext context, String label,
          {String? trailing, required VoidCallback onTap}) =>
      GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: rpx(32), vertical: rpx(30)),
          child: Row(
            children: [
              Expanded(
                child: Text(label,
                    style: TextStyle(
                        fontSize: rpx(30), color: BrandColors.textPrimary)),
              ),
              if (trailing != null) ...[
                Text(trailing,
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.textTertiary)),
                SizedBox(width: rpx(12)),
              ],
              const Icon(Icons.chevron_right, color: BrandColors.textTertiary),
            ],
          ),
        ),
      );
}
