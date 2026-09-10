import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/golf_options.dart';
import '../../../data/models/user.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../analysis/pages/history_page.dart';
import '../../auth/auth_controller.dart';
import '../../auth/pages/login_page.dart';
import '../../coach/pages/coach_page.dart';
import '../../discover/pages/courses_page.dart';
import '../../discover/pages/meetup_page.dart';
import '../../discover/pages/pros_page.dart';
import 'about_page.dart';
import 'account_deletion_page.dart';
import 'clubs_page.dart';
import 'edit_profile_page.dart';
import 'membership_page.dart';
import 'settings_page.dart';
import '../../../l10n/l10n.dart';

/// 我的：对照 client/src/pages/profile/index。头部资料卡 + 统计 + 档案 + 功能入口。
class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    if (!auth.isLoggedIn) {
      final inset = MediaQuery.of(context).padding;
      return Container(
        color: BrandColors.bgPage,
        padding: EdgeInsets.fromLTRB(rpx(32), inset.top + rpx(48), rpx(32), rpx(48)),
        child: Column(
          children: [
            Text(context.l10n.tabProfile,
                style: TextStyle(
                    fontSize: rpx(40),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.primary)),
            SizedBox(height: rpx(48)),
            Container(
              width: double.infinity,
              padding: EdgeInsets.all(rpx(40)),
              decoration: BoxDecoration(
                gradient: BrandColors.gradientHero,
                borderRadius: BorderRadius.circular(Radii.lg),
              ),
              child: Column(
                children: [
                  Text(context.l10n.profileSyncHint,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.onPrimary)),
                  SizedBox(height: rpx(28)),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(
                              builder: (_) => const LoginPage())),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: BrandColors.gold,
                        foregroundColor: Colors.black,
                      ),
                      child: Text(context.l10n.goLogin),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: rpx(24)),
            _menuGroup([
              _MenuItem(Icons.info_outline, context.l10n.aboutApp,
                  () => _go(context, const AboutPage())),
            ]),
          ],
        ),
      );
    }
    final user = auth.user;
    final inset = MediaQuery.of(context).padding;
    return Container(
      color: BrandColors.bgPage,
      child: ListView(
        padding: EdgeInsets.only(
          top: inset.top + rpx(24),
          left: rpx(32),
          right: rpx(32),
          bottom: rpx(48),
        ),
        children: [
          if (user?.accountDeletionScheduledAt != null) ...[
            _deletionBanner(context),
            SizedBox(height: rpx(20)),
          ],
          _header(context, user),
          SizedBox(height: rpx(24)),
          _statsRow(context, user),
          SizedBox(height: rpx(24)),
          _golfProfile(context, user),
          SizedBox(height: rpx(24)),
          _menuGroup([
            _MenuItem(Icons.description_outlined, context.l10n.myReports,
                () => _go(context, const HistoryPage())),
            _MenuItem(Icons.chat_bubble_outline, context.l10n.coachChat,
                () => _go(context, const CoachPage())),
            _MenuItem(Icons.card_membership, context.l10n.membershipCenter,
                () => _go(context, const MembershipPage())),
            _MenuItem(Icons.golf_course, context.l10n.myClubs,
                () => _go(context, const ClubsPage())),
          ]),
          SizedBox(height: rpx(24)),
          _menuGroup([
            _MenuItem(Icons.school_outlined, context.l10n.lessons,
                () => _go(context, const CoursesPage())),
            _MenuItem(Icons.sports_golf, context.l10n.proLibrary,
                () => _go(context, const ProsPage())),
            _MenuItem(Icons.groups_outlined, context.l10n.meetup,
                () => _go(context, const MeetupPage())),
          ]),
          SizedBox(height: rpx(24)),
          _menuGroup([
            _MenuItem(Icons.settings_outlined, context.l10n.settings,
                () => _go(context, const SettingsPage())),
            _MenuItem(Icons.info_outline, context.l10n.aboutApp,
                () => _go(context, const AboutPage())),
          ]),
          SizedBox(height: rpx(32)),
          _logoutButton(context),
        ],
      ),
    );
  }

  Widget _deletionBanner(BuildContext context) => GestureDetector(
        onTap: () => _go(context, const AccountDeletionPage()),
        child: Container(
          padding: EdgeInsets.all(rpx(24)),
          decoration: BoxDecoration(
            color: BrandColors.error.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(Radii.md),
            border: Border.all(color: BrandColors.error.withValues(alpha: 0.4)),
          ),
          child: Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: BrandColors.error),
              SizedBox(width: rpx(16)),
              Expanded(
                child: Text(context.l10n.deletionPending,
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.error)),
              ),
              const Icon(Icons.chevron_right, color: BrandColors.error),
            ],
          ),
        ),
      );

  Widget _header(BuildContext context, User? user) {
    return GestureDetector(
      onTap: () => _go(context, const EditProfilePage()),
      child: Container(
        padding: EdgeInsets.all(rpx(40)),
        decoration: BoxDecoration(
          gradient: BrandColors.gradientHero,
          borderRadius: BorderRadius.circular(Radii.lg),
        ),
        child: Row(
          children: [
            CircleAvatar(
              radius: rpx(56),
              backgroundColor: Colors.white24,
              backgroundImage: (user?.avatarUrl?.isNotEmpty ?? false)
                  ? CachedNetworkImageProvider(user!.avatarUrl!)
                  : null,
              child: (user?.avatarUrl?.isNotEmpty ?? false)
                  ? null
                  : Text((user?.nickname ?? context.l10n.golferFallback)
                      .characters
                      .first,
                      style: TextStyle(
                          fontSize: rpx(44),
                          color: Colors.white,
                          fontWeight: FontWeight.w700)),
            ),
            SizedBox(width: rpx(28)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(user?.nickname ?? context.l10n.golferFallback,
                      style: TextStyle(
                          fontSize: rpx(38),
                          fontWeight: FontWeight.w800,
                          color: Colors.white)),
                  SizedBox(height: rpx(10)),
                  _membershipBadge(context, user),
                ],
              ),
            ),
            Text(context.l10n.edit,
                style: TextStyle(color: BrandColors.onPrimaryMuted)),
            const Icon(Icons.chevron_right, color: BrandColors.onPrimaryMuted),
          ],
        ),
      ),
    );
  }

  Widget _membershipBadge(BuildContext context, User? user) {
    final l10n = context.l10n;
    if (user?.isMember == true) {
      final typeLabel = switch (user!.membershipType) {
        'annual' => l10n.memberYearly,
        'monthly' => l10n.memberMonthly,
        _ => l10n.memberGeneric,
      };
      return Container(
        padding: EdgeInsets.symmetric(horizontal: rpx(16), vertical: rpx(6)),
        decoration: BoxDecoration(
          color: BrandColors.gold,
          borderRadius: BorderRadius.circular(rpx(8)),
        ),
        child: Text(
            l10n.memberRemainingDays(typeLabel, user.membershipDaysRemaining),
            style: TextStyle(
                fontSize: rpx(22),
                color: Colors.black,
                fontWeight: FontWeight.w600)),
      );
    }
    return Text(l10n.freeUser,
        style:
            TextStyle(fontSize: rpx(26), color: BrandColors.onPrimaryMuted));
  }

  Widget _statsRow(BuildContext context, User? user) {
    final s = user?.stats;
    final l10n = context.l10n;
    return Container(
      padding: EdgeInsets.symmetric(vertical: rpx(28)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Row(
        children: [
          _stat(l10n.statAnalyses, '${s?.totalAnalyses ?? 0}'),
          _divider(),
          _stat(l10n.statCheckin, '${s?.streakDays ?? 0}'),
          _divider(),
          _stat(l10n.statHighScore,
              (s != null && s.bestScore > 0) ? '${s.bestScore.round()}' : '—'),
        ],
      ),
    );
  }

  Widget _divider() =>
      Container(width: 1, height: rpx(56), color: BrandColors.border);

  Widget _stat(String label, String value) => Expanded(
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    fontSize: rpx(44),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.primary)),
            SizedBox(height: rpx(8)),
            Text(label,
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.textSecondary)),
          ],
        ),
      );

  Widget _golfProfile(BuildContext context, User? user) {
    final l10n = context.l10n;
    final goalsText = (user?.primaryGoals.isNotEmpty ?? false)
        ? user!.primaryGoals.map((g) => localizedGoal(l10n, g)).join(l10n.listSep)
        : l10n.notSet;
    return Container(
      padding: EdgeInsets.all(rpx(32)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(l10n.golfProfile,
                  style: TextStyle(
                      fontSize: rpx(32),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              GestureDetector(
                onTap: () => _go(context, const EditProfilePage()),
                child: Text(l10n.modify,
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.primary)),
              ),
            ],
          ),
          SizedBox(height: rpx(20)),
          _profileRow(l10n.level, localizedLevel(l10n, user?.golfLevel)),
          _profileRow(l10n.goals, goalsText),
          _profileRow(
              l10n.practiceFreq, localizedFreq(l10n, user?.weeklyPracticeFrequency)),
        ],
      ),
    );
  }

  Widget _profileRow(String label, String value) => Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(10)),
        child: Row(
          children: [
            SizedBox(
              width: rpx(140),
              child: Text(label,
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textSecondary)),
            ),
            Expanded(
              child: Text(value,
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textPrimary)),
            ),
          ],
        ),
      );

  Widget _logoutButton(BuildContext context) => GestureDetector(
        onTap: () async {
          final ok = await showDialog<bool>(
            context: context,
            builder: (c) => AlertDialog(
              title: Text(context.l10n.prompt),
              content: Text(context.l10n.logoutConfirm),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(c, false),
                    child: Text(context.l10n.cancel)),
                TextButton(
                    onPressed: () => Navigator.pop(c, true),
                    child: Text(context.l10n.logout)),
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
          child: Text(context.l10n.logout,
              style: TextStyle(fontSize: rpx(32), color: BrandColors.error)),
        ),
      );

  void _go(BuildContext context, Widget page) =>
      Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));

  Widget _menuGroup(List<_MenuItem> items) {
    return Container(
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            if (i > 0)
              Divider(height: 1, color: BrandColors.divider, indent: rpx(80)),
            _menuRow(items[i]),
          ],
        ],
      ),
    );
  }

  Widget _menuRow(_MenuItem item) => GestureDetector(
        onTap: item.onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: rpx(32), vertical: rpx(30)),
          child: Row(
            children: [
              Icon(item.icon, color: BrandColors.primary, size: rpx(44)),
              SizedBox(width: rpx(24)),
              Expanded(
                child: Text(item.label,
                    style: TextStyle(
                        fontSize: rpx(30), color: BrandColors.textPrimary)),
              ),
              const Icon(Icons.chevron_right, color: BrandColors.textTertiary),
            ],
          ),
        ),
      );
}

class _MenuItem {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  _MenuItem(this.icon, this.label, this.onTap);
}
