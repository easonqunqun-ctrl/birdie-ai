import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/analysis_options.dart';
import '../../../core/swing_constants.dart';
import '../../../data/models/analysis.dart';
import '../../../data/repositories/analysis_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import 'report_page.dart';

/// 并排对比两份报告：对照 client/src/pages/analysis/compare。
class ComparePage extends StatefulWidget {
  const ComparePage({super.key, required this.leftId, required this.rightId});
  final String leftId;
  final String rightId;

  @override
  State<ComparePage> createState() => _ComparePageState();
}

class _ComparePageState extends State<ComparePage> {
  AnalysisReport? _earlier;
  AnalysisReport? _later;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final a = widget.leftId.trim();
    final b = widget.rightId.trim();
    if (a.isEmpty || b.isEmpty || a == b) {
      setState(() {
        _error = '请选择两篇不同的分析报告';
        _loading = false;
      });
      return;
    }
    if (a == 'sample' || b == 'sample') {
      setState(() {
        _error = '示例报告不支持并排对比';
        _loading = false;
      });
      return;
    }
    try {
      final repo = context.read<AnalysisRepository>();
      final ra = await repo.getReport(a);
      final rb = await repo.getReport(b);
      if (ra.status != 'completed' || rb.status != 'completed') {
        setState(() {
          _error = '仅支持对比已完成的分析报告';
          _loading = false;
        });
        return;
      }
      final ta = _ts(ra);
      final tb = _ts(rb);
      setState(() {
        if (ta <= tb) {
          _earlier = ra;
          _later = rb;
        } else {
          _earlier = rb;
          _later = ra;
        }
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = '加载失败，请重试';
        _loading = false;
      });
    }
  }

  int _ts(AnalysisReport r) {
    final iso = r.analyzedAt ?? r.createdAt;
    if (iso == null) return 0;
    return DateTime.tryParse(iso)?.millisecondsSinceEpoch ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('挥杆对比')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: BrandColors.error)))
              : _body(),
    );
  }

  Widget _body() {
    final e = _earlier!;
    final l = _later!;
    final delta = ((l.overallScore ?? 0) - (e.overallScore ?? 0)).round();
    return ListView(
      padding: EdgeInsets.all(rpx(32)),
      children: [
        Row(
          children: [
            Expanded(child: _scoreCol('较早', e)),
            Text(delta == 0 ? '—' : (delta > 0 ? '▲$delta' : '▼${delta.abs()}'),
                style: TextStyle(
                    fontSize: rpx(36),
                    fontWeight: FontWeight.w800,
                    color: delta > 0
                        ? BrandColors.success
                        : delta < 0
                            ? BrandColors.error
                            : BrandColors.textTertiary)),
            Expanded(child: _scoreCol('较近', l)),
          ],
        ),
        SizedBox(height: rpx(32)),
        Text('六维对比',
            style: TextStyle(
                fontSize: rpx(32),
                fontWeight: FontWeight.w700,
                color: BrandColors.primary)),
        SizedBox(height: rpx(16)),
        for (final k in kPhaseOrder)
          if (e.phaseScores.containsKey(k) || l.phaseScores.containsKey(k))
            _phaseRow(k, e.phaseScores[k]?.score, l.phaseScores[k]?.score),
        SizedBox(height: rpx(32)),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ReportPage(analysisId: e.id))),
                child: const Text('查看较早报告'),
              ),
            ),
            SizedBox(width: rpx(16)),
            Expanded(
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ReportPage(analysisId: l.id))),
                child: const Text('查看较近报告'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _scoreCol(String label, AnalysisReport r) => Column(
        children: [
          Text(label,
              style: TextStyle(fontSize: rpx(24), color: BrandColors.textTertiary)),
          SizedBox(height: rpx(8)),
          Text('${r.overallScore?.round() ?? '—'}',
              style: TextStyle(
                  fontSize: rpx(56),
                  fontWeight: FontWeight.w800,
                  color: BrandColors.primary)),
          Text(
              clubTypeLabels[r.clubType] ?? r.clubType,
              style: TextStyle(fontSize: rpx(22), color: BrandColors.textSecondary)),
        ],
      );

  Widget _phaseRow(String key, num? a, num? b) {
          final label = kPhaseLabel[key] ?? key;
    final da = (a ?? 0).toDouble();
    final db = (b ?? 0).toDouble();
    final d = (db - da).round();
    return Padding(
      padding: EdgeInsets.only(bottom: rpx(12)),
      child: Row(
        children: [
          SizedBox(
              width: rpx(120),
              child: Text(label,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary))),
          Expanded(
              child: Text('${a?.round() ?? '—'} → ${b?.round() ?? '—'}',
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textPrimary))),
          Text(d == 0 ? '0' : (d > 0 ? '+$d' : '$d'),
              style: TextStyle(
                  fontSize: rpx(26),
                  fontWeight: FontWeight.w700,
                  color: d > 0
                      ? BrandColors.success
                      : d < 0
                          ? BrandColors.error
                          : BrandColors.textTertiary)),
        ],
      ),
    );
  }
}
