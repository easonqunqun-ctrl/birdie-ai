import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/analysis_options.dart';
import '../../../core/swing_constants.dart';
import '../../../data/models/analysis.dart';
import '../../../data/repositories/analysis_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import 'capture_page.dart';
import 'report_page.dart';

/// 历史报告列表：对照 client/src/pages/analysis/history。
/// 分页 + 下拉刷新 + 触底加载 + 左滑删除 + 富卡片。
class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key});

  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  static const _pageSize = 20;
  final _scroll = ScrollController();
  final List<AnalysisListItem> _items = [];
  int _total = 0;
  int _page = 1;
  bool _loading = true;
  bool _loadingMore = false;
  Object? _error;

  bool get _hasMore => _items.length < _total;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    _loadFirst();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scroll.position.pixels >=
            _scroll.position.maxScrollExtent - rpx(200) &&
        _hasMore &&
        !_loadingMore) {
      _loadMore();
    }
  }

  Future<void> _loadFirst() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await context
          .read<AnalysisRepository>()
          .listAnalysesPage(page: 1, pageSize: _pageSize);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(res.items);
        _total = res.total;
        _page = 1;
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

  Future<void> _loadMore() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final res = await context
          .read<AnalysisRepository>()
          .listAnalysesPage(page: _page + 1, pageSize: _pageSize);
      if (!mounted) return;
      setState(() {
        _items.addAll(res.items);
        _total = res.total;
        _page += 1;
        _loadingMore = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _delete(AnalysisListItem it) async {
    if (it.status != 'completed' && it.status != 'failed') {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('分析进行中，完成后才可删除')));
      return;
    }
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除报告'),
        content: const Text('删除后无法在「我的报告」中查看此条记录，确认删除？'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('删除',
                  style: TextStyle(color: BrandColors.error))),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await context.read<AnalysisRepository>().deleteAnalysis(it.id);
      if (!mounted) return;
      setState(() {
        _items.removeWhere((e) => e.id == it.id);
        if (_total > 0) _total -= 1;
      });
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已删除')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('删除失败，请稍后再试')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('我的分析报告')),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(
                  valueColor:
                      AlwaysStoppedAnimation<Color>(BrandColors.primary)))
          : _error != null
              ? _errorView()
              : _items.isEmpty
                  ? _emptyView()
                  : RefreshIndicator(
                      onRefresh: _loadFirst,
                      color: BrandColors.primary,
                      child: ListView.separated(
                        controller: _scroll,
                        padding: EdgeInsets.all(rpx(32)),
                        itemCount: _items.length + 2,
                        separatorBuilder: (_, i) =>
                            SizedBox(height: i == 0 ? 0 : rpx(20)),
                        itemBuilder: (_, i) {
                          if (i == 0) return _summaryBar();
                          if (i == _items.length + 1) return _footer();
                          return _swipeItem(_items[i - 1]);
                        },
                      ),
                    ),
    );
  }

  Widget _summaryBar() => Padding(
        padding: EdgeInsets.only(bottom: rpx(20)),
        child: Text('$_total 条分析记录',
            style: TextStyle(
                fontSize: rpx(26), color: BrandColors.textSecondary)),
      );

  Widget _footer() {
    if (_loadingMore) {
      return Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(32)),
        child: const Center(
            child: CircularProgressIndicator(
                valueColor:
                    AlwaysStoppedAnimation<Color>(BrandColors.primary))),
      );
    }
    if (!_hasMore && _items.isNotEmpty) {
      return Padding(
        padding: EdgeInsets.symmetric(vertical: rpx(40)),
        child: Center(
            child: Text('— 没有更多了 —',
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.textTertiary))),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _swipeItem(AnalysisListItem it) => Dismissible(
        key: ValueKey(it.id),
        direction: DismissDirection.endToStart,
        confirmDismiss: (_) async {
          await _delete(it);
          return false;
        },
        background: Container(
          alignment: Alignment.centerRight,
          padding: EdgeInsets.only(right: rpx(40)),
          decoration: BoxDecoration(
            color: BrandColors.error,
            borderRadius: BorderRadius.circular(Radii.lg),
          ),
          child: const Text('删除',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
        ),
        child: _item(it),
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
            OutlinedButton(onPressed: _loadFirst, child: const Text('重新加载')),
          ],
        ),
      );

  Widget _emptyView() => Center(
        child: Padding(
          padding: EdgeInsets.all(rpx(48)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('⛳️', style: TextStyle(fontSize: rpx(96))),
              SizedBox(height: rpx(20)),
              Text('还没有分析记录',
                  style: TextStyle(
                      fontSize: rpx(34),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              SizedBox(height: rpx(12)),
              Text('拍一段挥杆视频，AI 会给你完整的动作诊断与训练建议。',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary)),
              SizedBox(height: rpx(32)),
              ElevatedButton(
                onPressed: () => Navigator.of(context).pushReplacement(
                    MaterialPageRoute(builder: (_) => const CapturePage())),
                child: const Text('开始分析'),
              ),
            ],
          ),
        ),
      );

  Widget _item(AnalysisListItem it) {
    final level = it.scoreLevel ?? scoreLevelFromScore(it.overallScore);
    final meta = level != null ? kScoreLevelMeta[level] : null;
    final completed = it.status == 'completed';
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ReportPage(analysisId: it.id))),
      child: Container(
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
            SizedBox(width: rpx(24)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(clubTypeLabels[it.clubType] ?? it.clubType,
                          style: TextStyle(
                              fontSize: rpx(30),
                              fontWeight: FontWeight.w600,
                              color: BrandColors.textPrimary)),
                      if (!completed) ...[
                        SizedBox(width: rpx(12)),
                        _statusTag(it.status),
                      ],
                    ],
                  ),
                  SizedBox(height: rpx(10)),
                  Text(_fmtDate(it.createdAt ?? it.analyzedAt),
                      style: TextStyle(
                          fontSize: rpx(24),
                          color: BrandColors.textTertiary)),
                  if (it.scoreChange != null && it.scoreChange != 0) ...[
                    SizedBox(height: rpx(8)),
                    Text(
                      '${it.scoreChange! > 0 ? '▲' : '▼'} ${it.scoreChange!.abs()}',
                      style: TextStyle(
                          fontSize: rpx(22),
                          color: it.scoreChange! > 0
                              ? BrandColors.success
                              : BrandColors.error),
                    ),
                  ],
                ],
              ),
            ),
            if (completed && it.overallScore != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('${it.overallScore!.round()}',
                      style: TextStyle(
                          fontSize: rpx(52),
                          fontWeight: FontWeight.w800,
                          color: meta?.color ?? BrandColors.primary)),
                  if (meta != null)
                    Text(meta.label,
                        style: TextStyle(
                            fontSize: rpx(20),
                            color: BrandColors.textTertiary)),
                ],
              )
            else
              Text('—',
                  style: TextStyle(
                      fontSize: rpx(44), color: BrandColors.textTertiary)),
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
        child: Text(meta?.emoji ?? '⛳️', style: TextStyle(fontSize: rpx(48))),
      );

  Widget _statusTag(String status) {
    final failed = status == 'failed';
    final color = failed ? BrandColors.error : BrandColors.warning;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: rpx(12), vertical: rpx(4)),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(rpx(8)),
      ),
      child: Text(failed ? '失败' : '分析中',
          style: TextStyle(fontSize: rpx(20), color: color)),
    );
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
