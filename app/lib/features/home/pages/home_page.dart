import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/analysis_options.dart';
import '../../../core/swing_constants.dart';
import '../../../data/models/analysis.dart';
import '../../../data/models/user.dart';
import '../../../data/repositories/analysis_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../nav/require_login.dart';
import '../../../widgets/brand_logo.dart';
import '../../analysis/pages/capture_page.dart';
import '../../analysis/pages/history_page.dart';
import '../../analysis/pages/report_page.dart';
import '../../auth/auth_controller.dart';
import '../../auth/pages/login_page.dart';
import '../../coach/pages/coach_page.dart';
import '../../legal/pages/legal_page.dart';
import '../../profile/pages/membership_page.dart';
import '../../profile/pages/profile_page.dart';
import '../../../l10n/l10n.dart';

/// 首页：对照 client/src/pages/index（登录态 + 访客态）。
class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List<AnalysisListItem> _recent = const [];
  bool _loadingRecent = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    final auth = context.read<AuthController>();
    if (!auth.isLoggedIn) {
      if (!mounted) return;
      setState(() {
        _recent = const [];
        _loadingRecent = false;
      });
      return;
    }
    final repo = context.read<AnalysisRepository>();
    // 并行拉用户态 + 最近报告，避免串行等满 2×RTT 像卡住
    final results = await Future.wait<Object?>([
      auth.refresh().then((_) => null).catchError((_) => null),
      repo.listAnalyses(page: 1, pageSize: 3).then<Object?>((v) => v).catchError((_) => null),
    ]);
    if (!mounted) return;
    final list = results[1];
    setState(() {
      if (list is List<AnalysisListItem>) _recent = list;
      _loadingRecent = false;
    });
  }

  void _goLogin() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const LoginPage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final user = auth.user;
    final loggedIn = auth.isLoggedIn;
    final inset = MediaQuery.of(context).padding;
    return Container(
      color: BrandColors.bgPage,
      child: RefreshIndicator(
        onRefresh: _refresh,
        color: BrandColors.primary,
        child: ListView(
          padding: EdgeInsets.only(
            top: inset.top + rpx(20),
            left: rpx(32),
            right: rpx(32),
            bottom: rpx(48),
          ),
          children: loggedIn
              ? [
                  _topBar(user),
                  SizedBox(height: rpx(24)),
                  _hero(user),
                  SizedBox(height: rpx(24)),
                  _statsRow(user),
                  SizedBox(height: rpx(24)),
                  _quickRow(user),
                  SizedBox(height: rpx(32)),
                  _recentSection(),
                ]
              : [
                  _guestTopBar(),
                  SizedBox(height: rpx(24)),
                  _guestHero(),
                  SizedBox(height: rpx(24)),
                  _guestFeatures(),
                  SizedBox(height: rpx(24)),
                  _guestQuicks(),
                  SizedBox(height: rpx(32)),
                  _guestLegal(),
                ],
        ),
      ),
    );
  }

  Widget _guestTopBar() => Row(
        children: [
          _brandMark(),
          SizedBox(width: rpx(16)),
          Text.rich(
            TextSpan(
              children: [
                TextSpan(
                    text: context.l10n.appNameShort,
                    style: TextStyle(
                        fontSize: rpx(38),
                        fontWeight: FontWeight.w900,
                        color: BrandColors.primary)),
                TextSpan(
                    text: context.l10n.appNameAccent,
                    style: TextStyle(
                        fontSize: rpx(38),
                        fontWeight: FontWeight.w900,
                        color: BrandColors.accentMint)),
              ],
            ),
          ),
          const Spacer(),
          GestureDetector(
            onTap: _goLogin,
            child: Container(
              padding:
                  EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(12)),
              decoration: BoxDecoration(
                color: BrandColors.primaryTint,
                borderRadius: BorderRadius.circular(rpx(32)),
              ),
              child: Text(context.l10n.login,
                  style: TextStyle(
                      fontSize: rpx(28),
                      fontWeight: FontWeight.w600,
                      color: BrandColors.primary)),
            ),
          ),
        ],
      );

  Widget _brandMark() => BrandLogo(size: rpx(72));

  Widget _guestHero() => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(40)),
        decoration: BoxDecoration(
          gradient: BrandColors.gradientHero,
          borderRadius: BorderRadius.circular(Radii.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.l10n.welcomeUse,
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
            SizedBox(height: rpx(12)),
            Text(context.l10n.guestSubtitle1,
                style: TextStyle(
                    fontSize: rpx(40),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.onPrimary)),
            Text(context.l10n.guestSubtitle2,
                style: TextStyle(
                    fontSize: rpx(40),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.onPrimary)),
            SizedBox(height: rpx(16)),
            Text(context.l10n.guestLegalHint,
                style: TextStyle(
                    fontSize: rpx(26),
                    height: 1.45,
                    color: BrandColors.onPrimaryMuted)),
            SizedBox(height: rpx(28)),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _goLogin,
                style: _heroCtaStyle(),
                child: Text(context.l10n.loginToAnalyze,
                    style: TextStyle(
                        fontSize: rpx(30), fontWeight: FontWeight.w800)),
              ),
            ),
          ],
        ),
      );

  Widget _guestFeatures() => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(32)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.l10n.productOffers,
                style: TextStyle(
                    fontSize: rpx(30),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            SizedBox(height: rpx(16)),
            _guestFeature('📹', context.l10n.guestFeatSwing),
            _guestFeature('💬', context.l10n.guestFeatCoach),
            _guestFeature('📈', context.l10n.guestFeatPlan),
          ],
        ),
      );

  Widget _guestFeature(String icon, String text) => Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(10)),
        child: Row(
          children: [
            Text(icon, style: TextStyle(fontSize: rpx(36))),
            SizedBox(width: rpx(16)),
            Expanded(
              child: Text(text,
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textSecondary)),
            ),
          ],
        ),
      );

  Widget _guestQuicks() => Column(
        children: [
          _quickRowCard(
            emoji: '🎬',
            title: context.l10n.sampleReportTitle,
            sub: context.l10n.sampleReportSubGuest,
            iconTint: BrandColors.accentMintDim,
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const ReportPage(analysisId: 'sample'))),
          ),
          SizedBox(height: rpx(12)),
          _quickRowCard(
            emoji: '💬',
            title: context.l10n.coachIntroTitle,
            sub: context.l10n.coachIntroSub,
            iconTint: BrandColors.primaryTint,
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const CoachPage())),
          ),
        ],
      );

  Widget _guestLegal() => Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const LegalPage(kind: LegalKind.terms))),
            child: Text(context.l10n.userAgreement,
                style: TextStyle(
                    fontSize: rpx(26),
                    color: BrandColors.primary,
                    fontWeight: FontWeight.w600)),
          ),
          Text(' · ',
              style: TextStyle(
                  fontSize: rpx(26), color: BrandColors.textTertiary)),
          GestureDetector(
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const LegalPage(kind: LegalKind.privacy))),
            child: Text(context.l10n.privacyPolicy,
                style: TextStyle(
                    fontSize: rpx(26),
                    color: BrandColors.primary,
                    fontWeight: FontWeight.w600)),
          ),
        ],
      );

  // -------------------- 顶栏 --------------------
  Widget _topBar(User? user) {
    return Row(
      children: [
        _brandMark(),
        SizedBox(width: rpx(16)),
        Text.rich(
          TextSpan(
            children: [
              TextSpan(
                  text: context.l10n.appNameShort,
                  style: TextStyle(
                      fontSize: rpx(38),
                      fontWeight: FontWeight.w900,
                      color: BrandColors.primary)),
              TextSpan(
                  text: context.l10n.appNameAccent,
                  style: TextStyle(
                      fontSize: rpx(38),
                      fontWeight: FontWeight.w900,
                      color: BrandColors.accentMint)),
            ],
          ),
        ),
        const Spacer(),
        GestureDetector(
          onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ProfilePage())),
          child: CircleAvatar(
            radius: rpx(32),
            backgroundColor: BrandColors.primaryTint,
            backgroundImage: (user?.avatarUrl?.isNotEmpty ?? false)
                ? CachedNetworkImageProvider(user!.avatarUrl!)
                : null,
            child: (user?.avatarUrl?.isNotEmpty ?? false)
                ? null
                : Text(
                    (user?.nickname?.isNotEmpty ?? false)
                        ? user!.nickname!.characters.first
                        : context.l10n.golferFallback.characters.first,
                    style: const TextStyle(color: BrandColors.primary)),
          ),
        ),
      ],
    );
  }

  /// 靛蓝 Hero 上的反色 CTA：白底 + 主色字，对齐小程序 `home__hero-cta`。
  ButtonStyle _heroCtaStyle() {
    return ElevatedButton.styleFrom(
      backgroundColor: BrandColors.onPrimary,
      foregroundColor: BrandColors.primary,
      disabledBackgroundColor: BrandColors.onPrimary.withValues(alpha: 0.7),
      disabledForegroundColor: BrandColors.primary.withValues(alpha: 0.5),
      elevation: 4,
      shadowColor: Colors.black.withValues(alpha: 0.28),
      padding: EdgeInsets.symmetric(vertical: rpx(24)),
      shape: StadiumBorder(
        side: BorderSide(color: BrandColors.primaryTint, width: rpx(2)),
      ),
    );
  }

  // -------------------- Hero --------------------
  Widget _hero(User? user) {
    final latest = _recent.isNotEmpty ? _recent.first : null;
    final scoreMode = latest != null &&
        latest.status == 'completed' &&
        latest.overallScore != null;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(40)),
      decoration: BoxDecoration(
        gradient: BrandColors.gradientHero,
        borderRadius: BorderRadius.circular(Radii.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (scoreMode)
            _heroScore(latest)
          else
            _heroGreeting(user),
          SizedBox(height: rpx(28)),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => _startAnalysis(user),
              style: _heroCtaStyle(),
              child: Text(scoreMode ? context.l10n.uploadNewSwing : context.l10n.startFirstAnalysis,
                  style: TextStyle(
                      fontSize: rpx(30), fontWeight: FontWeight.w800)),
            ),
          ),
          SizedBox(height: rpx(12)),
          Text(_quotaLine(user),
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.onPrimaryMuted)),
        ],
      ),
    );
  }

  Widget _heroGreeting(User? user) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(context.l10n.helloGolfer(user?.nickname ?? context.l10n.golferFallback),
              style: TextStyle(
                  fontSize: rpx(44),
                  fontWeight: FontWeight.w800,
                  color: BrandColors.onPrimary)),
          SizedBox(height: rpx(12)),
          Text(context.l10n.heroCta,
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.onPrimaryMuted)),
        ],
      );

  Widget _heroScore(AnalysisListItem latest) {
    final level = latest.scoreLevel ?? scoreLevelFromScore(latest.overallScore);
    final meta = level != null ? kScoreLevelMeta[level] : null;
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${meta?.emoji ?? '⛳️'} ${context.l10n.latestShot}',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
              SizedBox(height: rpx(8)),
              Text(meta?.label ?? context.l10n.analysisDone,
                  style: TextStyle(
                      fontSize: rpx(38),
                      fontWeight: FontWeight.w800,
                      color: BrandColors.onPrimary)),
              SizedBox(height: rpx(4)),
              Text(clubTypeLabels[latest.clubType] ?? latest.clubType,
                  style: TextStyle(
                      fontSize: rpx(24), color: BrandColors.onPrimaryMuted)),
            ],
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text('${latest.overallScore?.round()}',
                    style: TextStyle(
                        fontSize: rpx(88),
                        height: 1,
                        fontWeight: FontWeight.w800,
                        color: BrandColors.onPrimary)),
                Text(context.l10n.scoreUnit,
                    style: TextStyle(
                        fontSize: rpx(24),
                        color: BrandColors.onPrimaryMuted)),
              ],
            ),
            if (latest.scoreChange != null && latest.scoreChange != 0)
              Text(
                '${latest.scoreChange! > 0 ? '▲' : '▼'} ${latest.scoreChange!.abs()}',
                style: TextStyle(
                    fontSize: rpx(26),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.onPrimary),
              ),
          ],
        ),
      ],
    );
  }

  String _quotaLine(User? user) {
    final q = user?.quota;
    if (q == null) return '';
    final en = context.l10n.localeName.toLowerCase().startsWith('en');
    final offer = user?.marketOffer;
    if (q.analysisRemaining < 0) {
      return en ? 'Unlimited analyses' : '分析次数无限';
    }
    if (offer?.isWelcome == true) {
      final n = offer!.intlWelcomeRemaining ?? q.analysisRemaining;
      final t = offer.intlWelcomeTotal;
      return en ? 'Trial left: $n/$t' : '试用剩余 $n / $t 次';
    }
    if ((user?.isMember ?? false) || q.analysisRemaining < 0) {
      return context.l10n.quotaMemberUnlimited;
    }
    return context.l10n.quotaMonthRemaining(q.analysisRemaining, q.analysisTotal);
  }

  // -------------------- 统计 --------------------
  Widget _statsRow(User? user) {
    final s = user?.stats;
    return Container(
      padding: EdgeInsets.symmetric(vertical: rpx(28)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Row(
        children: [
          _stat(context.l10n.statTotalAnalyses, '${s?.totalAnalyses ?? 0}'),
          _divider(),
          _stat(context.l10n.statBestScore,
              (s != null && s.bestScore > 0) ? '${s.bestScore.round()}' : '—'),
          _divider(),
          _stat(context.l10n.statStreak, '${s?.streakDays ?? 0}'),
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
                    fontSize: rpx(48),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.primary)),
            SizedBox(height: rpx(8)),
            Text(label,
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.textSecondary)),
          ],
        ),
      );

  // -------------------- 快捷入口（对照小程序纵向 quick 行） --------------------
  Widget _quickRow(User? user) {
    final showSample = !(user?.hasCompletedRealAnalysis ?? false);
    final chatText = (user?.isMember ?? false) ||
            (user?.quota?.chatRemainingToday ?? 0) < 0
        ? context.l10n.memberUnlimited
        : context.l10n.chatRemainingToday(user?.quota?.chatRemainingToday ?? 0);
    return Column(
      children: [
        _quickRowCard(
          emoji: '💬',
          title: context.l10n.askCoach,
          sub: chatText,
          iconTint: BrandColors.primaryTint,
          onTap: () => Navigator.of(context)
              .push(MaterialPageRoute(builder: (_) => const CoachPage())),
        ),
        if (showSample) ...[
          SizedBox(height: rpx(12)),
          _quickRowCard(
            emoji: '🎬',
            title: context.l10n.sampleReportTitle,
            sub: context.l10n.sampleReportSubUser,
            iconTint: BrandColors.accentMintDim,
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const ReportPage(analysisId: 'sample'))),
          ),
        ],
      ],
    );
  }

  Widget _quickRowCard({
    required String emoji,
    required String title,
    required String sub,
    required Color iconTint,
    required VoidCallback onTap,
  }) =>
      GestureDetector(
        onTap: onTap,
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: rpx(24), vertical: rpx(20)),
          decoration: BoxDecoration(
            color: BrandColors.bgCard,
            borderRadius: BorderRadius.circular(Radii.md),
            border: Border.all(color: BrandColors.border),
          ),
          child: Row(
            children: [
              Container(
                width: rpx(64),
                height: rpx(64),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: iconTint,
                  borderRadius: BorderRadius.circular(rpx(16)),
                ),
                child: Text(emoji, style: TextStyle(fontSize: rpx(32))),
              ),
              SizedBox(width: rpx(20)),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: TextStyle(
                            fontSize: rpx(30),
                            fontWeight: FontWeight.w700,
                            color: BrandColors.primary)),
                    SizedBox(height: rpx(4)),
                    Text(sub,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: rpx(26),
                            color: BrandColors.textTertiary)),
                  ],
                ),
              ),
              Text('›',
                  style: TextStyle(
                      fontSize: rpx(38),
                      fontWeight: FontWeight.w300,
                      color: BrandColors.textTertiary)),
            ],
          ),
        ),
      );

  // -------------------- 最近分析 --------------------
  Widget _recentSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(context.l10n.recentAnalyses,
                style: TextStyle(
                    fontSize: rpx(34),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            if (_recent.isNotEmpty)
              GestureDetector(
                onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const HistoryPage())),
                child: Text(context.l10n.viewAll,
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.primary)),
              ),
          ],
        ),
        SizedBox(height: rpx(16)),
        if (_loadingRecent)
          const Center(
              child: Padding(
            padding: EdgeInsets.all(24),
            child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(BrandColors.primary)),
          ))
        else if (_recent.isEmpty)
          Container(
            width: double.infinity,
            padding: EdgeInsets.all(rpx(48)),
            decoration: BoxDecoration(
              color: BrandColors.bgCard,
              borderRadius: BorderRadius.circular(Radii.lg),
              border: Border.all(color: BrandColors.border),
            ),
            child: Column(
              children: [
                Text('⛳️', style: TextStyle(fontSize: rpx(56))),
                SizedBox(height: rpx(12)),
                Text(context.l10n.noAnalysesYet,
                    style: TextStyle(
                        fontSize: rpx(26), color: BrandColors.textSecondary)),
              ],
            ),
          )
        else
          ..._recent.map(_recentItem),
      ],
    );
  }

  Widget _recentItem(AnalysisListItem it) {
    final level = it.scoreLevel ?? scoreLevelFromScore(it.overallScore);
    final meta = level != null ? kScoreLevelMeta[level] : null;
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => ReportPage(analysisId: it.id))),
      child: Container(
        margin: EdgeInsets.only(bottom: rpx(16)),
        padding: EdgeInsets.all(rpx(20)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(Radii.md),
              child: (it.thumbnailUrl?.isNotEmpty ?? false)
                  ? CachedNetworkImage(
                      imageUrl: it.thumbnailUrl!,
                      width: rpx(120),
                      height: rpx(120),
                      fit: BoxFit.cover,
                      errorWidget: (_, _, _) => _thumbFallback(meta),
                    )
                  : _thumbFallback(meta),
            ),
            SizedBox(width: rpx(20)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(clubTypeLabels[it.clubType] ?? it.clubType,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.textPrimary)),
                  SizedBox(height: rpx(8)),
                  Text(_fmtDate(it.createdAt ?? it.analyzedAt),
                      style: TextStyle(
                          fontSize: rpx(24),
                          color: BrandColors.textTertiary)),
                ],
              ),
            ),
            if (it.status == 'completed' && it.overallScore != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('${it.overallScore!.round()}',
                      style: TextStyle(
                          fontSize: rpx(48),
                          fontWeight: FontWeight.w800,
                          color: meta?.color ?? BrandColors.primary)),
                  Text(meta?.label ?? '',
                      style: TextStyle(
                          fontSize: rpx(20),
                          color: BrandColors.textTertiary)),
                ],
              )
            else
              Text(it.status == 'failed' ? context.l10n.statusFailed : context.l10n.statusAnalyzing,
                  style: TextStyle(
                      fontSize: rpx(24),
                      color: it.status == 'failed'
                          ? BrandColors.error
                          : BrandColors.warning)),
          ],
        ),
      ),
    );
  }

  Widget _thumbFallback(ScoreLevelMeta? meta) => Container(
        width: rpx(120),
        height: rpx(120),
        alignment: Alignment.center,
        color: BrandColors.primaryTint,
        child: Text(meta?.emoji ?? '⛳️', style: TextStyle(fontSize: rpx(44))),
      );

  // -------------------- 动作 --------------------
  Future<void> _startAnalysis(User? user) async {
    if (!context.read<AuthController>().isLoggedIn) {
      final ok = await requireLogin(context);
      if (!ok || !mounted) return;
    }
    final q = user?.quota ?? context.read<AuthController>().user?.quota;
    final u = user ?? context.read<AuthController>().user;
    final exhausted = q != null &&
        !(u?.isMember ?? false) &&
        q.analysisRemaining == 0;
    if (exhausted) {
      if (!mounted) return;
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(context.l10n.quotaExhaustedTitle),
          content: Text(context.l10n.quotaExhaustedBody),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(context.l10n.gotIt)),
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const MembershipPage()));
              },
              child: Text(context.l10n.viewBenefits),
            ),
          ],
        ),
      );
      return;
    }
    if (!mounted) return;
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const CapturePage()));
  }

  String _fmtDate(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    final d = DateTime.tryParse(iso)?.toLocal();
    if (d == null) return '';
    final now = DateTime.now();
    String two(int n) => n.toString().padLeft(2, '0');
    if (d.year == now.year && d.month == now.month && d.day == now.day) {
      return context.l10n.todayAt('${two(d.hour)}:${two(d.minute)}');
    }
    if (d.year == now.year) {
      return '${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
    }
    return '${d.year}-${two(d.month)}-${two(d.day)}';
  }
}
