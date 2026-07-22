import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/drill_library.dart';
import '../../../core/practice_calendar_layout.dart';
import '../../../data/models/training.dart';
import '../../../data/repositories/training_repository.dart';
import '../../../data/repositories/user_repository.dart';
import '../../../nav/require_login.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/practice_calendar.dart';
import '../../../widgets/progress_line_chart.dart';
import '../../analysis/pages/capture_page.dart';
import '../../auth/auth_controller.dart';
import '../../auth/pages/login_page.dart';

/// 训练：对照 client training — 计划 + 打卡月历 + 进步曲线。
class TrainingPage extends StatefulWidget {
  const TrainingPage({super.key});

  @override
  State<TrainingPage> createState() => _TrainingPageState();
}

class _TrainingPageState extends State<TrainingPage> {
  TrainingPlan? _plan;
  bool _loading = true;
  Object? _error;
  final Set<String> _expanded = {};
  String? _submitting;

  String _monthKey = monthKeyNow();
  PracticeCalendarGrid _calendar =
      buildPracticeCalendarGrid(monthKeyNow(), {});
  List<ProgressChartPoint> _progressPoints = const [];
  int _progressWindowDays = 90;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    final auth = context.read<AuthController>();
    if (!auth.isLoggedIn) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = null;
        _plan = null;
        _progressPoints = const [];
        _calendar = buildPracticeCalendarGrid(_monthKey, {});
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final trainingRepo = context.read<TrainingRepository>();
      final userRepo = context.read<UserRepository>();
      final plan = await trainingRepo.getCurrentPlan();
      await _loadCalendar(trainingRepo);
      await _loadProgress(userRepo);
      if (!mounted) return;
      setState(() {
        _plan = plan;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  Future<void> _loadCalendar(TrainingRepository repo) async {
    try {
      final logs = await repo.getPracticeLogs(_monthKey);
      final counts = aggregatePracticeCounts(logs);
      if (!mounted) return;
      setState(() {
        _calendar =
            buildPracticeCalendarGrid(_monthKey, counts, localDateKey());
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _calendar = buildPracticeCalendarGrid(_monthKey, {});
      });
    }
  }

  Future<void> _loadProgress(UserRepository repo) async {
    try {
      final points = await repo.getAnalysisProgress(
          windowDays: _progressWindowDays > 0 ? _progressWindowDays : null);
      final chart = points
          .map((p) {
            final at = DateTime.tryParse(p.analyzedAt)?.toLocal() ??
                DateTime.now();
            return ProgressChartPoint(at: at, score: p.overallScore);
          })
          .toList()
        ..sort((a, b) => a.at.compareTo(b.at));
      if (!mounted) return;
      setState(() => _progressPoints = chart);
    } catch (_) {
      if (!mounted) return;
      setState(() => _progressPoints = const []);
    }
  }

  Future<void> _shiftMonth(int delta) async {
    final next = shiftMonthKey(_monthKey, delta);
    final now = monthKeyNow();
    if (delta > 0 && next.compareTo(now) > 0) return;
    setState(() => _monthKey = next);
    await _loadCalendar(context.read<TrainingRepository>());
  }

  Future<void> _complete(TrainingTask t) async {
    setState(() => _submitting = t.id);
    try {
      final streak =
          await context.read<TrainingRepository>().completeTask(t.id);
      if (!mounted) return;
      await _reload();
      if (!mounted) return;
      _showDoneModal(streak);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('打卡失败，请稍后重试')));
    } finally {
      if (mounted) setState(() => _submitting = null);
    }
  }

  void _showDoneModal(int? streak) {
    showDialog<void>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(streak != null && streak > 0 ? '打卡成功！连续 $streak 天' : '打卡成功！'),
        content: const Text('建议用相同机位再拍一次挥杆，对比是否改善。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c), child: const Text('稍后再说')),
          TextButton(
            onPressed: () {
              Navigator.pop(c);
              Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const CapturePage()));
            },
            child: const Text('去拍摄'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loggedIn = context.watch<AuthController>().isLoggedIn;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('训练')),
      body: !loggedIn
          ? _guest()
          : _loading
              ? const Center(
                  child: CircularProgressIndicator(
                      valueColor: AlwaysStoppedAnimation<Color>(
                          BrandColors.primary)))
              : _error != null
                  ? _errorView()
                  : RefreshIndicator(
                      onRefresh: _reload,
                      color: BrandColors.primary,
                      child: ListView(
                        padding: EdgeInsets.all(rpx(32)),
                        children: [
                          _calendarCard(),
                          SizedBox(height: rpx(24)),
                          _progressCard(),
                          SizedBox(height: rpx(24)),
                          if (_plan == null || _plan!.tasks.isEmpty)
                            _emptyInline()
                          else
                            ..._planSections(_plan!),
                        ],
                      ),
                    ),
    );
  }

  Widget _guest() => Center(
        child: Padding(
          padding: EdgeInsets.all(rpx(48)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.fitness_center_outlined,
                  size: rpx(100), color: BrandColors.textTertiary),
              SizedBox(height: rpx(24)),
              Text('登录后查看训练计划',
                  style: TextStyle(
                      fontSize: rpx(34),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              SizedBox(height: rpx(12)),
              Text('打卡日历与进步曲线也会在登录后展示',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary)),
              SizedBox(height: rpx(32)),
              ElevatedButton(
                onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const LoginPage())),
                child: const Text('去登录'),
              ),
            ],
          ),
        ),
      );

  Widget _calendarCard() => Container(
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('练习日历',
                style: TextStyle(
                    fontSize: rpx(30),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            SizedBox(height: rpx(12)),
            PracticeCalendar(
              grid: _calendar,
              embedded: true,
              canGoNext: _monthKey.compareTo(monthKeyNow()) < 0,
              onPrevMonth: () => _shiftMonth(-1),
              onNextMonth: () => _shiftMonth(1),
            ),
          ],
        ),
      );

  Widget _progressCard() {
    final isMember =
        context.watch<AuthController>().user?.isMember ?? false;
    return Container(
      padding: EdgeInsets.all(rpx(28)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('进步曲线',
                  style: TextStyle(
                      fontSize: rpx(30),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              const Spacer(),
              _windowPill(90, '近 90 天'),
              SizedBox(width: rpx(12)),
              _windowPill(0, '全部'),
            ],
          ),
          SizedBox(height: rpx(16)),
          if (!isMember && _progressPoints.isEmpty)
            Text('完成分析后可查看得分趋势；会员可见更完整曲线。',
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.textSecondary))
          else
            ProgressLineChart(points: _progressPoints),
        ],
      ),
    );
  }

  Widget _windowPill(int days, String label) {
    final active = _progressWindowDays == days;
    return GestureDetector(
      onTap: () async {
        if (_progressWindowDays == days) return;
        setState(() => _progressWindowDays = days);
        await _loadProgress(context.read<UserRepository>());
      },
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: rpx(18), vertical: rpx(8)),
        decoration: BoxDecoration(
          color: active ? BrandColors.primaryTint : BrandColors.bgSubtle,
          borderRadius: BorderRadius.circular(rpx(24)),
          border: Border.all(
              color: active ? BrandColors.primary : BrandColors.border),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: rpx(22),
                fontWeight: FontWeight.w600,
                color: active
                    ? BrandColors.primary
                    : BrandColors.textSecondary)),
      ),
    );
  }

  List<Widget> _planSections(TrainingPlan plan) {
    final streak =
        context.watch<AuthController>().user?.stats?.streakDays ?? 0;
    final groups = _groupByDate(plan.tasks);
    return [
      _weekProgressCard(plan, streak),
      if (plan.aiSummary != null && plan.aiSummary!.isNotEmpty) ...[
        SizedBox(height: rpx(24)),
        _summaryCard(plan.aiSummary!),
      ],
      SizedBox(height: rpx(32)),
      for (final g in groups) ...[
        _dayHeader(g.key, g.value.length),
        SizedBox(height: rpx(12)),
        ...g.value.map(_taskCard),
        SizedBox(height: rpx(16)),
      ],
    ];
  }

  Widget _emptyInline() => Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(48)),
        child: Column(
          children: [
            Text('还没有训练计划',
                style: TextStyle(
                    fontSize: rpx(34),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            SizedBox(height: rpx(12)),
            Text('先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.textSecondary)),
            SizedBox(height: rpx(28)),
            ElevatedButton(
              onPressed: () async {
                final ok = await requireLogin(context);
                if (!ok || !mounted) return;
                Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const CapturePage()));
              },
              child: const Text('去上传视频'),
            ),
          ],
        ),
      );

  List<MapEntry<String, List<TrainingTask>>> _groupByDate(
      List<TrainingTask> tasks) {
    final map = <String, List<TrainingTask>>{};
    for (final t in tasks) {
      map.putIfAbsent(t.scheduledDate, () => []).add(t);
    }
    final keys = map.keys.toList()..sort();
    return [for (final k in keys) MapEntry(k, map[k]!)];
  }

  Widget _dayHeader(String date, int count) => Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(_dayLabel(date),
              style: TextStyle(
                  fontSize: rpx(32),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.textPrimary)),
          Text('$count 个任务',
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.textTertiary)),
        ],
      );

  Widget _errorView() => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('😣', style: TextStyle(fontSize: rpx(80))),
            SizedBox(height: rpx(20)),
            Text('加载失败，请稍后再试',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
            SizedBox(height: rpx(24)),
            OutlinedButton(onPressed: _reload, child: const Text('重新加载')),
          ],
        ),
      );

  Widget _weekProgressCard(TrainingPlan plan, int streak) {
    final ratio =
        plan.totalTasks == 0 ? 0.0 : plan.completedTasks / plan.totalTasks;
    return Container(
      padding: EdgeInsets.all(rpx(40)),
      decoration: BoxDecoration(
        gradient: BrandColors.gradientHero,
        borderRadius: BorderRadius.circular(Radii.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('本周训练',
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.onPrimaryMuted)),
              if (_weekRange(plan).isNotEmpty)
                Text(_weekRange(plan),
                    style: TextStyle(
                        fontSize: rpx(24), color: BrandColors.onPrimaryMuted)),
            ],
          ),
          SizedBox(height: rpx(12)),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text('${plan.completedTasks} / ${plan.totalTasks}',
                  style: TextStyle(
                      fontSize: rpx(64),
                      fontWeight: FontWeight.w800,
                      color: BrandColors.onPrimary)),
              SizedBox(width: rpx(12)),
              Text('已完成',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.onPrimaryMuted)),
            ],
          ),
          SizedBox(height: rpx(20)),
          ClipRRect(
            borderRadius: BorderRadius.circular(rpx(8)),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: rpx(12),
              backgroundColor: Colors.white24,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(BrandColors.accentMint),
            ),
          ),
          if (streak > 0) ...[
            SizedBox(height: rpx(16)),
            Text('连续打卡 $streak 天',
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.onPrimaryMuted)),
          ],
        ],
      ),
    );
  }

  Widget _summaryCard(String summary) => Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Text(summary,
            style: TextStyle(
                fontSize: rpx(28),
                height: 1.5,
                color: BrandColors.textSecondary)),
      );

  Widget _taskCard(TrainingTask t) {
    final drill = getDrillDetail(t.drillId);
    final expanded = _expanded.contains(t.id);
    final submitting = _submitting == t.id;
    return Container(
      margin: EdgeInsets.only(bottom: rpx(12)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          ListTile(
            onTap: () => setState(() {
              if (expanded) {
                _expanded.remove(t.id);
              } else {
                _expanded.add(t.id);
              }
            }),
            title: Text(drill.name,
                style: TextStyle(
                    fontSize: rpx(30),
                    fontWeight: FontWeight.w600,
                    decoration:
                        t.isCompleted ? TextDecoration.lineThrough : null,
                    color: BrandColors.textPrimary)),
            subtitle: Text(t.isCompleted ? '已完成' : '待完成',
                style: TextStyle(
                    fontSize: rpx(24),
                    color: t.isCompleted
                        ? BrandColors.success
                        : BrandColors.textTertiary)),
            trailing: Icon(
              expanded ? Icons.expand_less : Icons.expand_more,
              color: BrandColors.textTertiary,
            ),
          ),
          if (expanded)
            Padding(
              padding: EdgeInsets.fromLTRB(rpx(28), 0, rpx(28), rpx(28)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (drill.description.isNotEmpty)
                    Text(drill.description,
                        style: TextStyle(
                            fontSize: rpx(26),
                            height: 1.45,
                            color: BrandColors.textSecondary)),
                  if (!t.isCompleted) ...[
                    SizedBox(height: rpx(20)),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: submitting ? null : () => _complete(t),
                        child: Text(submitting ? '提交中…' : '完成打卡'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  String _dayLabel(String date) {
    final d = DateTime.tryParse(date);
    if (d == null) return date;
    const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
    return '${d.month}/${d.day} 周${weekdays[d.weekday - 1]}';
  }

  String _weekRange(TrainingPlan plan) {
    if (plan.weekStart.isEmpty) return '';
    final a = DateTime.tryParse(plan.weekStart);
    final b = DateTime.tryParse(plan.weekEnd);
    if (a == null || b == null) return '';
    return '${a.month}/${a.day} – ${b.month}/${b.day}';
  }
}
