import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/drill_library.dart';
import '../../../data/models/training.dart';
import '../../../data/repositories/training_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../analysis/pages/capture_page.dart';
import '../../auth/auth_controller.dart';

/// 训练：对照 client/src/pages/training/index。当周计划 + 按天分组 + 展开打卡。
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

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final plan = await context.read<TrainingRepository>().getCurrentPlan();
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
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('训练')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(
                  valueColor:
                      AlwaysStoppedAnimation<Color>(BrandColors.primary)))
          : _error != null
              ? _errorView()
              : (_plan == null || _plan!.tasks.isEmpty)
                  ? _empty()
                  : _planView(_plan!),
    );
  }

  Widget _planView(TrainingPlan plan) {
    final streak =
        context.watch<AuthController>().user?.stats?.streakDays ?? 0;
    final groups = _groupByDate(plan.tasks);
    return RefreshIndicator(
      onRefresh: _reload,
      color: BrandColors.primary,
      child: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          _progressCard(plan, streak),
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
        ],
      ),
    );
  }

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

  Widget _empty() => Center(
        child: Padding(
          padding: EdgeInsets.all(rpx(48)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.fitness_center_outlined,
                  size: rpx(120), color: BrandColors.textTertiary),
              SizedBox(height: rpx(24)),
              Text('还没有训练计划',
                  style: TextStyle(
                      fontSize: rpx(36),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              SizedBox(height: rpx(12)),
              Text('先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textSecondary)),
              SizedBox(height: rpx(32)),
              ElevatedButton(
                onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const CapturePage())),
                child: const Text('去上传视频'),
              ),
            ],
          ),
        ),
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

  Widget _progressCard(TrainingPlan plan, int streak) {
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
              minHeight: rpx(14),
              backgroundColor: Colors.white24,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(BrandColors.accentMint),
            ),
          ),
          if (streak > 0) ...[
            SizedBox(height: rpx(16)),
            Text('🔥 连续训练 $streak 天',
                style: TextStyle(
                    fontSize: rpx(26), color: BrandColors.onPrimary)),
          ],
        ],
      ),
    );
  }

  Widget _summaryCard(String summary) => Container(
        padding: EdgeInsets.all(rpx(32)),
        decoration: BoxDecoration(
          color: BrandColors.primaryTint,
          borderRadius: BorderRadius.circular(Radii.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.lightbulb_outline,
                    color: BrandColors.primary, size: 20),
                SizedBox(width: rpx(12)),
                Text('教练本周提示',
                    style: TextStyle(
                        fontSize: rpx(28),
                        fontWeight: FontWeight.w700,
                        color: BrandColors.primaryDark)),
              ],
            ),
            SizedBox(height: rpx(12)),
            Text(summary,
                style: TextStyle(
                    fontSize: rpx(28),
                    height: 1.6,
                    color: BrandColors.primaryDark)),
          ],
        ),
      );

  Widget _taskCard(TrainingTask t) {
    final d = getDrillDetail(t.drillId);
    final done = t.isCompleted;
    final open = _expanded.contains(t.id);
    final submitting = _submitting == t.id;
    return Container(
      margin: EdgeInsets.only(bottom: rpx(16)),
      decoration: BoxDecoration(
        color: done ? BrandColors.accentMintDim : BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(
            color: done
                ? BrandColors.success.withValues(alpha: 0.3)
                : BrandColors.border),
      ),
      child: Column(
        children: [
          GestureDetector(
            onTap: () => setState(() {
              open ? _expanded.remove(t.id) : _expanded.add(t.id);
            }),
            child: Padding(
              padding: EdgeInsets.all(rpx(28)),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(d.name,
                            style: TextStyle(
                                fontSize: rpx(30),
                                fontWeight: FontWeight.w700,
                                color: BrandColors.textPrimary)),
                        SizedBox(height: rpx(8)),
                        Text(
                            '${d.durationMinutes} 分钟 · ${d.difficulty} · ${d.sets} 组',
                            style: TextStyle(
                                fontSize: rpx(24),
                                color: BrandColors.textSecondary)),
                        if (t.coachNote != null && t.coachNote!.isNotEmpty) ...[
                          SizedBox(height: rpx(8)),
                          Text(t.coachNote!,
                              style: TextStyle(
                                  fontSize: rpx(24),
                                  color: BrandColors.textSecondary)),
                        ],
                      ],
                    ),
                  ),
                  SizedBox(width: rpx(12)),
                  if (done)
                    Icon(Icons.check_circle,
                        color: BrandColors.success, size: rpx(52))
                  else
                    Icon(open ? Icons.expand_less : Icons.expand_more,
                        color: BrandColors.textTertiary),
                ],
              ),
            ),
          ),
          if (open && !done) _taskDetail(t, d, submitting),
          if (done && t.completedAt != null)
            Padding(
              padding: EdgeInsets.fromLTRB(rpx(28), 0, rpx(28), rpx(20)),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('已于 ${t.completedAt!.split('T').first} 完成',
                    style: TextStyle(
                        fontSize: rpx(22), color: BrandColors.success)),
              ),
            ),
        ],
      ),
    );
  }

  Widget _taskDetail(TrainingTask t, DrillDetail d, bool submitting) => Padding(
        padding: EdgeInsets.fromLTRB(rpx(28), 0, rpx(28), rpx(28)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(d.description,
                style: TextStyle(
                    fontSize: rpx(26),
                    height: 1.5,
                    color: BrandColors.textSecondary)),
            SizedBox(height: rpx(16)),
            for (var i = 0; i < d.steps.length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: rpx(10)),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: rpx(36),
                      height: rpx(36),
                      alignment: Alignment.center,
                      decoration: const BoxDecoration(
                          color: BrandColors.primaryTint,
                          shape: BoxShape.circle),
                      child: Text('${i + 1}',
                          style: TextStyle(
                              fontSize: rpx(22),
                              color: BrandColors.primary,
                              fontWeight: FontWeight.w700)),
                    ),
                    SizedBox(width: rpx(16)),
                    Expanded(
                      child: Text(d.steps[i],
                          style: TextStyle(
                              fontSize: rpx(26),
                              height: 1.5,
                              color: BrandColors.textSecondary)),
                    ),
                  ],
                ),
              ),
            if (d.tips.isNotEmpty) ...[
              SizedBox(height: rpx(8)),
              Text('教练提示',
                  style: TextStyle(
                      fontSize: rpx(26),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              SizedBox(height: rpx(8)),
              for (final tip in d.tips)
                Padding(
                  padding: EdgeInsets.only(bottom: rpx(6)),
                  child: Text('· $tip',
                      style: TextStyle(
                          fontSize: rpx(24),
                          height: 1.5,
                          color: BrandColors.textSecondary)),
                ),
            ],
            SizedBox(height: rpx(20)),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: submitting ? null : () => _complete(t),
                child: submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('完成打卡'),
              ),
            ),
          ],
        ),
      );

  String _weekRange(TrainingPlan plan) {
    final s = DateTime.tryParse(plan.weekStart);
    final e = DateTime.tryParse(plan.weekEnd);
    if (s == null || e == null) return '';
    return '${s.month}.${s.day} - ${e.month}.${e.day}';
  }

  String _dayLabel(String date) {
    final d = DateTime.tryParse(date);
    if (d == null) return date;
    final now = DateTime.now();
    if (d.year == now.year && d.month == now.month && d.day == now.day) {
      return '今天';
    }
    const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
    return '${d.month}月${d.day}日 周${weekdays[d.weekday - 1]}';
  }
}
