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
import '../../analysis/pages/capture_page.dart';
import '../../analysis/pages/history_page.dart';
import '../../analysis/pages/report_page.dart';
import '../../auth/auth_controller.dart';
import '../../coach/pages/coach_page.dart';
import '../../profile/pages/membership_page.dart';
import '../../profile/pages/profile_page.dart';

/// 首页：对照 client/src/pages/index/index.tsx（登录态）。
/// 顶栏 → hero（评分/问候双态）→ 三项统计 → 快捷入口 → 最近分析。
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
    final repo = context.read<AnalysisRepository>();
    await auth.refresh();
    try {
      final list = await repo.listAnalyses(page: 1, pageSize: 3);
      if (!mounted) return;
      setState(() {
        _recent = list;
        _loadingRecent = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingRecent = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthController>().user;
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
          children: [
            _topBar(user),
            SizedBox(height: rpx(24)),
            _hero(user),
            SizedBox(height: rpx(24)),
            _statsRow(user),
            SizedBox(height: rpx(24)),
            _quickRow(user),
            SizedBox(height: rpx(32)),
            _recentSection(),
          ],
        ),
      ),
    );
  }

  // -------------------- 顶栏 --------------------
  Widget _topBar(User? user) {
    return Row(
      children: [
        Text('领翼golf',
            style: TextStyle(
                fontSize: rpx(40),
                fontWeight: FontWeight.w800,
                color: BrandColors.primary)),
        const Spacer(),
        GestureDetector(
          onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ProfilePage())),
          child: CircleAvatar(
            radius: rpx(40),
            backgroundColor: BrandColors.primaryTint,
            backgroundImage: (user?.avatarUrl?.isNotEmpty ?? false)
                ? CachedNetworkImageProvider(user!.avatarUrl!)
                : null,
            child: (user?.avatarUrl?.isNotEmpty ?? false)
                ? null
                : Text(
                    (user?.nickname?.isNotEmpty ?? false)
                        ? user!.nickname!.characters.first
                        : '球',
                    style: const TextStyle(color: BrandColors.primary)),
          ),
        ),
      ],
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
              style: ElevatedButton.styleFrom(
                backgroundColor: BrandColors.gold,
                foregroundColor: Colors.black,
                padding: EdgeInsets.symmetric(vertical: rpx(24)),
              ),
              child: Text(scoreMode ? '+ 上传新挥杆' : '🎬 开始第一次分析',
                  style: TextStyle(
                      fontSize: rpx(30), fontWeight: FontWeight.w700)),
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
          Text('你好，${user?.nickname ?? '球友'} 👋',
              style: TextStyle(
                  fontSize: rpx(44),
                  fontWeight: FontWeight.w800,
                  color: BrandColors.onPrimary)),
          SizedBox(height: rpx(12)),
          Text('拍一段挥杆，30 秒拿到 AI 专属报告',
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
              Text('${meta?.emoji ?? '⛳️'} 最近一杆',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
              SizedBox(height: rpx(8)),
              Text(meta?.label ?? '已完成分析',
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
                Text(' 分',
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
    if ((user?.isMember ?? false) || q.analysisRemaining < 0) {
      return '会员 · 挥杆分析无限次';
    }
    return '本月剩余分析 ${q.analysisRemaining}/${q.analysisTotal} 次';
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
          _stat('累计分析', '${s?.totalAnalyses ?? 0}'),
          _divider(),
          _stat('最佳得分',
              (s != null && s.bestScore > 0) ? '${s.bestScore.round()}' : '—'),
          _divider(),
          _stat('连续天数', '${s?.streakDays ?? 0}'),
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

  // -------------------- 快捷入口 --------------------
  Widget _quickRow(User? user) {
    final showSample = !(user?.hasCompletedRealAnalysis ?? false);
    final chatText = (user?.isMember ?? false) ||
            (user?.quota?.chatRemainingToday ?? 0) < 0
        ? '会员无限次'
        : '今日剩余 ${user?.quota?.chatRemainingToday ?? 0} 次';
    return Row(
      children: [
        Expanded(
          child: _quickCard(
            icon: Icons.chat_bubble_outline,
            title: '问 AI 教练',
            sub: chatText,
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const CoachPage())),
          ),
        ),
        if (showSample) ...[
          SizedBox(width: rpx(20)),
          Expanded(
            child: _quickCard(
              icon: Icons.play_circle_outline,
              title: '示例报告',
              sub: '先看看 AI 能发现什么',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => const ReportPage(analysisId: 'sample'))),
            ),
          ),
        ],
      ],
    );
  }

  Widget _quickCard(
          {required IconData icon,
          required String title,
          required String sub,
          required VoidCallback onTap}) =>
      GestureDetector(
        onTap: onTap,
        child: Container(
          padding: EdgeInsets.all(rpx(28)),
          decoration: BoxDecoration(
            color: BrandColors.bgCard,
            borderRadius: BorderRadius.circular(Radii.lg),
            border: Border.all(color: BrandColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: BrandColors.primary, size: rpx(44)),
              SizedBox(height: rpx(16)),
              Text(title,
                  style: TextStyle(
                      fontSize: rpx(30),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              SizedBox(height: rpx(6)),
              Text(sub,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: rpx(22), color: BrandColors.textSecondary)),
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
            Text('最近分析',
                style: TextStyle(
                    fontSize: rpx(34),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            if (_recent.isNotEmpty)
              GestureDetector(
                onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const HistoryPage())),
                child: Text('查看全部 ›',
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
                Text('还没有分析记录，上传第一段挥杆吧',
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
              Text(it.status == 'failed' ? '失败' : '分析中',
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
  void _startAnalysis(User? user) {
    final q = user?.quota;
    final exhausted = q != null &&
        !(user?.isMember ?? false) &&
        q.analysisRemaining == 0;
    if (exhausted) {
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('本月分析次数已用完'),
          content: const Text('升级会员即可享受无限次挥杆分析。'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('我知道了')),
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const MembershipPage()));
              },
              child: const Text('开通会员'),
            ),
          ],
        ),
      );
      return;
    }
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
      return '今天 ${two(d.hour)}:${two(d.minute)}';
    }
    if (d.year == now.year) {
      return '${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
    }
    return '${d.year}-${two(d.month)}-${two(d.day)}';
  }
}
