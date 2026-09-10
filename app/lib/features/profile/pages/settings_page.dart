import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/app_info.dart';
import '../../../core/locale_controller.dart';
import '../../../core/storage.dart';
import '../../../l10n/l10n.dart';
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
    final l10n = context.l10n;
    final localeCtl = context.watch<LocaleController>();
    final langLabel = switch (localeCtl.preference) {
      'en' => l10n.languageEn,
      'zh' => l10n.languageZh,
      _ => l10n.languageSystem,
    };
    return Scaffold(
      appBar: AppBar(title: Text(l10n.settings)),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          _sectionTitle(l10n.sectionExperience),
          _group([
            _row(context, l10n.language,
                trailing: langLabel, onTap: () => _pickLanguage(context)),
            _divider(),
            _row(context, l10n.replayCaptureGuide,
                onTap: () => _replayGuide(context)),
            _divider(),
            _row(context, l10n.clearCache, onTap: () => _clearCache(context)),
          ]),
          SizedBox(height: rpx(32)),
          _sectionTitle(l10n.sectionLegal),
          _group([
            _row(context, l10n.userAgreement,
                onTap: () =>
                    _go(context, const LegalPage(kind: LegalKind.terms))),
            _divider(),
            _row(context, l10n.privacyPolicy,
                onTap: () =>
                    _go(context, const LegalPage(kind: LegalKind.privacy))),
            _divider(),
            _row(context, l10n.aboutApp,
                trailing: 'v$kClientVersion',
                onTap: () => _go(context, const AboutPage())),
          ]),
          SizedBox(height: rpx(32)),
          _group([
            _row(context, l10n.deleteAccount,
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

  Future<void> _pickLanguage(BuildContext context) async {
    final l10n = context.l10n;
    final ctl = context.read<LocaleController>();
    final picked = await showModalBottomSheet<String>(
      context: context,
      builder: (c) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: Text(l10n.languageSystem),
              onTap: () => Navigator.pop(c, ''),
            ),
            ListTile(
              title: Text(l10n.languageZh),
              onTap: () => Navigator.pop(c, 'zh'),
            ),
            ListTile(
              title: Text(l10n.languageEn),
              onTap: () => Navigator.pop(c, 'en'),
            ),
          ],
        ),
      ),
    );
    if (picked != null && context.mounted) {
      await ctl.setPreference(picked);
    }
  }

  Future<void> _replayGuide(BuildContext context) async {
    await AppStorage.instance.clearAnalysisGuideSeen();
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(context.l10n.guideResetToast)));
  }

  Future<void> _clearCache(BuildContext context) async {
    final l10n = context.l10n;
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(l10n.clearCache),
        content: Text(l10n.clearCacheBody),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: Text(l10n.cancel)),
          TextButton(
              onPressed: () => Navigator.pop(c, true),
              child: Text(l10n.confirmClear)),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    await AppStorage.instance.clearAnalysisGuideSeen();
    if (context.mounted) await context.read<AuthController>().logout();
  }

  Widget _logoutButton(BuildContext context) {
    final l10n = context.l10n;
    return GestureDetector(
      onTap: () async {
        final ok = await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
            title: Text(l10n.prompt),
            content: Text(l10n.logoutConfirm),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(c, false),
                  child: Text(l10n.cancel)),
              TextButton(
                  onPressed: () => Navigator.pop(c, true),
                  child: Text(l10n.logout)),
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
        child: Text(l10n.logout,
            style: TextStyle(fontSize: rpx(32), color: BrandColors.error)),
      ),
    );
  }

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
