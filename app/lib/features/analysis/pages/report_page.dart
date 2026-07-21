import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../../../core/analysis_options.dart';
import '../../../core/drill_library.dart';
import '../../../core/swing_constants.dart';
import '../../../data/models/analysis.dart';
import '../../../data/repositories/training_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../coach/pages/coach_page.dart';
import '../analysis_controller.dart';
import 'capture_page.dart';

/// 报告页：对照 client/src/pages/analysis/report。
/// 视频回放（阶段色条 + 倍速）+ 分级评分卡 + 六维雷达 + 问题诊断 + 训练建议 + 底部动作。
class ReportPage extends StatefulWidget {
  const ReportPage({super.key, required this.analysisId});
  final String analysisId;

  @override
  State<ReportPage> createState() => _ReportPageState();
}

class _ReportPageState extends State<ReportPage> {
  AnalysisReport? _report;
  Object? _error;
  bool _loading = true;

  VideoPlayerController? _video;
  bool _videoReady = false;
  double _rate = 1.0;
  String _playbackSource = 'skeleton'; // skeleton | original
  bool _showHidden = false;
  bool _syncing = false;

  bool get _isSample => widget.analysisId == 'sample';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r =
          await context.read<AnalysisController>().loadReport(widget.analysisId);
      if (!mounted) return;
      setState(() {
        _report = r;
        _loading = false;
      });
      _initVideo(r);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  bool get _canToggleSource =>
      (_report?.skeletonVideoUrl?.isNotEmpty ?? false) &&
      (_report?.videoUrl.isNotEmpty ?? false);

  String _resolveSrc(AnalysisReport r) {
    if (_playbackSource == 'skeleton' &&
        (r.skeletonVideoUrl?.isNotEmpty ?? false)) {
      return r.skeletonVideoUrl!;
    }
    return r.videoUrl;
  }

  Future<void> _initVideo(AnalysisReport r) async {
    final src = _resolveSrc(r);
    if (src.isEmpty) return;
    final old = _video;
    _video = null;
    _videoReady = false;
    await old?.dispose();
    final ctl = VideoPlayerController.networkUrl(Uri.parse(src));
    try {
      await ctl.initialize();
      await ctl.setPlaybackSpeed(_rate);
      if (!mounted) {
        await ctl.dispose();
        return;
      }
      setState(() {
        _video = ctl;
        _videoReady = true;
      });
    } catch (_) {
      // 骨骼片放不了则回退原片
      if (_playbackSource == 'skeleton' && r.videoUrl.isNotEmpty) {
        _playbackSource = 'original';
        await ctl.dispose();
        await _initVideo(r);
      }
    }
  }

  Future<void> _switchSource(String s) async {
    if (s == _playbackSource) return;
    _playbackSource = s;
    if (_report != null) await _initVideo(_report!);
  }

  void _seekTo(num seconds) {
    final v = _video;
    if (v == null || !_videoReady) return;
    v.seekTo(Duration(milliseconds: (seconds * 1000).round()));
    v.play();
    setState(() {});
  }

  Future<void> _setRate(double r) async {
    setState(() => _rate = r);
    await _video?.setPlaybackSpeed(r);
  }

  @override
  void dispose() {
    _video?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(
        title: Text(
            '${clubTypeLabels[_report?.clubType] ?? '挥杆'}分析报告'),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(
                  valueColor:
                      AlwaysStoppedAnimation<Color>(BrandColors.primary)))
          : (_error != null || _report == null)
              ? _errorView()
              : _reportView(_report!),
    );
  }

  Widget _errorView() => Center(
        child: Padding(
          padding: EdgeInsets.all(rpx(48)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline, size: rpx(80), color: BrandColors.error),
              SizedBox(height: rpx(24)),
              Text('报告加载失败',
                  style: TextStyle(
                      fontSize: rpx(32), color: BrandColors.textPrimary)),
              SizedBox(height: rpx(24)),
              TextButton(onPressed: _load, child: const Text('重试')),
            ],
          ),
        ),
      );

  // -------------------- 主体 --------------------
  Widget _reportView(AnalysisReport r) {
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        if (_isSample) _sampleBanner(),
        _videoBlock(r),
        Padding(
          padding: EdgeInsets.all(rpx(32)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _scoreCard(r),
              if (r.analysisConfidence != null) ...[
                SizedBox(height: rpx(24)),
                _trustBadge(r),
              ],
              if (r.phaseHighlights.isNotEmpty) ...[
                SizedBox(height: rpx(24)),
                _highlights(r.phaseHighlights),
              ],
              if (r.qualityWarnings.isNotEmpty) ...[
                SizedBox(height: rpx(24)),
                _qualityWarnings(r.qualityWarnings),
              ],
              SizedBox(height: rpx(24)),
              _metaRow(r),
              if (r.phaseScores.isNotEmpty) ...[
                SizedBox(height: rpx(32)),
                _radarSection(r),
              ],
              ..._issuesSection(r),
              ..._recommendationsSection(r),
              SizedBox(height: rpx(40)),
              _footer(r),
              SizedBox(height: rpx(48)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _sampleBanner() => Container(
        width: double.infinity,
        color: BrandColors.primaryTint,
        padding: EdgeInsets.symmetric(horizontal: rpx(32), vertical: rpx(20)),
        child: Row(
          children: [
            const Text('🎬'),
            SizedBox(width: rpx(16)),
            Expanded(
              child: Text('这是演示报告，用真实数据展示 AI 能发现的问题；不消耗你的分析次数。',
                  style: TextStyle(
                      fontSize: rpx(24), color: BrandColors.textSecondary)),
            ),
          ],
        ),
      );

  // -------------------- 视频区 --------------------
  Widget _videoBlock(AnalysisReport r) {
    final v = _video;
    return Container(
      color: Colors.black,
      child: Column(
        children: [
          AspectRatio(
            aspectRatio: (v != null && _videoReady && v.value.aspectRatio > 0)
                ? v.value.aspectRatio
                : 16 / 9,
            child: (v != null && _videoReady)
                ? GestureDetector(
                    onTap: () {
                      setState(() {
                        v.value.isPlaying ? v.pause() : v.play();
                      });
                    },
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        VideoPlayer(v),
                        if (!v.value.isPlaying)
                          Container(
                            width: rpx(96),
                            height: rpx(96),
                            decoration: BoxDecoration(
                              color: Colors.black45,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.play_arrow,
                                color: Colors.white, size: 44),
                          ),
                        Positioned(
                          left: 0,
                          right: 0,
                          bottom: 0,
                          child: VideoProgressIndicator(
                            v,
                            allowScrubbing: true,
                            colors: const VideoProgressColors(
                              playedColor: BrandColors.gold,
                              bufferedColor: Colors.white24,
                              backgroundColor: Colors.white10,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )
                : (r.thumbnailUrl?.isNotEmpty ?? false)
                    ? Image.network(r.thumbnailUrl!, fit: BoxFit.contain)
                    : const Center(
                        child: Icon(Icons.videocam_off, color: Colors.white38)),
          ),
          if (r.phaseTimestamps.isNotEmpty) _phaseBar(r),
          _controlsRow(r),
        ],
      ),
    );
  }

  Widget _phaseBar(AnalysisReport r) {
    final present =
        kPhaseOrder.where((k) => r.phaseTimestamps.containsKey(k)).toList();
    final total = present.fold<double>(0, (acc, k) {
      final w = r.phaseTimestamps[k]!;
      return acc + (w.end - w.start);
    });
    return Row(
      children: [
        for (final k in present)
          Expanded(
            flex: total > 0
                ? (((r.phaseTimestamps[k]!.end - r.phaseTimestamps[k]!.start) /
                            total) *
                        1000)
                    .round()
                    .clamp(1, 1000)
                : 1,
            child: GestureDetector(
              onTap: () => _seekTo(r.phaseTimestamps[k]!.start),
              child: Container(
                height: rpx(52),
                alignment: Alignment.center,
                color: kPhaseColor[k],
                child: Text(kPhaseLabel[k] ?? k,
                    style: TextStyle(
                        fontSize: rpx(20),
                        color: Colors.white,
                        fontWeight: FontWeight.w600)),
              ),
            ),
          ),
      ],
    );
  }

  Widget _controlsRow(AnalysisReport r) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: rpx(24), vertical: rpx(16)),
      child: Row(
        children: [
          if (_canToggleSource) ...[
            _pill('原片', _playbackSource == 'original',
                () => _switchSource('original')),
            SizedBox(width: rpx(12)),
            _pill('骨骼', _playbackSource == 'skeleton',
                () => _switchSource('skeleton')),
            const Spacer(),
          ] else
            const Spacer(),
          Text('倍速',
              style: TextStyle(fontSize: rpx(22), color: Colors.white54)),
          SizedBox(width: rpx(12)),
          for (final rate in const [0.5, 1.0, 1.5, 2.0]) ...[
            _pill('${rate == rate.toInt() ? rate.toInt() : rate}×',
                _rate == rate, () => _setRate(rate)),
            SizedBox(width: rpx(8)),
          ],
        ],
      ),
    );
  }

  Widget _pill(String text, bool active, VoidCallback onTap) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding:
              EdgeInsets.symmetric(horizontal: rpx(20), vertical: rpx(8)),
          decoration: BoxDecoration(
            color: active ? BrandColors.gold : Colors.white12,
            borderRadius: BorderRadius.circular(rpx(24)),
          ),
          child: Text(text,
              style: TextStyle(
                  fontSize: rpx(22),
                  color: active ? Colors.black : Colors.white70,
                  fontWeight: FontWeight.w600)),
        ),
      );

  // -------------------- 分级评分卡 --------------------
  Widget _scoreCard(AnalysisReport r) {
    final level = r.scoreLevel ?? scoreLevelFromScore(r.overallScore);
    final meta = level != null ? kScoreLevelMeta[level] : null;
    final bg = meta?.color ?? BrandColors.primary;
    final fg = meta?.textColor ?? BrandColors.onPrimary;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(40)),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(Radii.lg),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(meta?.emoji ?? '⛳️',
                    style: TextStyle(fontSize: rpx(48))),
                SizedBox(height: rpx(8)),
                Text(meta?.label ?? '分析完成',
                    style: TextStyle(
                        fontSize: rpx(38),
                        fontWeight: FontWeight.w800,
                        color: fg)),
                SizedBox(height: rpx(8)),
                if (meta?.caption != null)
                  Text(meta!.caption,
                      style: TextStyle(
                          fontSize: rpx(24),
                          color: fg.withValues(alpha: 0.85))),
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
                  Text(r.overallScore?.round().toString() ?? '—',
                      style: TextStyle(
                          fontSize: rpx(104),
                          height: 1.0,
                          fontWeight: FontWeight.w800,
                          color: fg)),
                  SizedBox(width: rpx(6)),
                  Text('分',
                      style: TextStyle(
                          fontSize: rpx(28),
                          color: fg.withValues(alpha: 0.85))),
                ],
              ),
              if (r.scoreChange != null && r.scoreChange != 0)
                Text(
                  '${r.scoreChange! > 0 ? '▲' : '▼'} ${r.scoreChange!.abs()}',
                  style: TextStyle(
                      fontSize: rpx(28),
                      fontWeight: FontWeight.w700,
                      color: fg),
                ),
              if (r.scoreChange != null)
                Text('较最近一次同类型',
                    style: TextStyle(
                        fontSize: rpx(20),
                        color: fg.withValues(alpha: 0.7))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _trustBadge(AnalysisReport r) {
    final c = r.analysisConfidence!.toDouble();
    final (label, color) = c >= 0.75
        ? ('AI 高可信', BrandColors.success)
        : c >= 0.5
            ? ('AI 中等可信', BrandColors.warning)
            : ('AI 可信度较低', BrandColors.error);
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(24)),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(Radii.md),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(Icons.verified_outlined, color: color, size: rpx(36)),
          SizedBox(width: rpx(16)),
          Expanded(
            child: Text('$label · 置信度 ${(c * 100).round()}%',
                style: TextStyle(
                    fontSize: rpx(26),
                    fontWeight: FontWeight.w600,
                    color: BrandColors.textPrimary)),
          ),
          if (c < 0.5 && !_isSample)
            TextButton(
              onPressed: _shootAgain,
              child: const Text('重拍一段'),
            ),
        ],
      ),
    );
  }

  Widget _highlights(List<String> lines) => _noticeCard(
      '本次亮点', lines, BrandColors.success, BrandColors.accentMintDim);

  Widget _qualityWarnings(List<String> lines) => _noticeCard(
      '拍摄提示', lines, BrandColors.warning,
      BrandColors.warning.withValues(alpha: 0.08));

  Widget _noticeCard(String title, List<String> lines, Color accent, Color bg) =>
      Container(
        width: double.infinity,
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(Radii.md),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: TextStyle(
                    fontSize: rpx(26),
                    fontWeight: FontWeight.w700,
                    color: accent)),
            SizedBox(height: rpx(12)),
            for (final l in lines)
              Padding(
                padding: EdgeInsets.only(bottom: rpx(6)),
                child: Text('· $l',
                    style: TextStyle(
                        fontSize: rpx(24),
                        height: 1.5,
                        color: BrandColors.textSecondary)),
              ),
          ],
        ),
      );

  Widget _metaRow(AnalysisReport r) => Wrap(
        spacing: rpx(24),
        runSpacing: rpx(12),
        children: [
          _metaChip('📷 ${cameraAngleLabels[r.cameraAngle] ?? r.cameraAngle}'),
          _metaChip('🏌️ ${clubTypeLabels[r.clubType] ?? r.clubType}'),
          if (r.videoDuration != null)
            _metaChip('⏱ ${r.videoDuration!.toStringAsFixed(1)}s'),
        ],
      );

  Widget _metaChip(String t) => Text(t,
      style: TextStyle(fontSize: rpx(24), color: BrandColors.textSecondary));

  // -------------------- 六维雷达 + 阶段列表 --------------------
  Widget _radarSection(AnalysisReport r) {
    final entries = kPhaseOrder
        .where((k) => r.phaseScores.containsKey(k))
        .map((k) => MapEntry(k, r.phaseScores[k]!))
        .toList();
    final data = entries.isNotEmpty
        ? entries
        : r.phaseScores.entries.toList();
    return _sectionCard(
      title: '六维评分',
      hint: '点击阶段跳到对应画面',
      child: Column(
        children: [
          SizedBox(
            height: rpx(480),
            child: RadarChart(
              RadarChartData(
                radarShape: RadarShape.polygon,
                tickCount: 4,
                ticksTextStyle:
                    const TextStyle(color: Colors.transparent, fontSize: 1),
                radarBorderData:
                    const BorderSide(color: BrandColors.border, width: 1),
                gridBorderData:
                    const BorderSide(color: BrandColors.border, width: 1),
                tickBorderData:
                    const BorderSide(color: BrandColors.border, width: 1),
                titlePositionPercentageOffset: 0.12,
                getTitle: (index, angle) => RadarChartTitle(
                    text: index < data.length ? data[index].value.label : ''),
                titleTextStyle: TextStyle(
                    fontSize: rpx(22), color: BrandColors.textSecondary),
                dataSets: [
                  RadarDataSet(
                    fillColor: BrandColors.primary.withValues(alpha: 0.18),
                    borderColor: BrandColors.primary,
                    borderWidth: 2,
                    entryRadius: 3,
                    dataEntries: [
                      for (final e in data)
                        RadarEntry(value: e.value.score.toDouble()),
                    ],
                  ),
                ],
              ),
            ),
          ),
          SizedBox(height: rpx(16)),
          ...data.map((e) => _phaseRow(e.key, e.value)),
        ],
      ),
    );
  }

  Widget _phaseRow(String key, PhaseScore ps) => GestureDetector(
        onTap: () {
          final ts = _report?.phaseTimestamps[key];
          if (ts != null) _seekTo(ts.start);
        },
        child: Container(
          padding: EdgeInsets.symmetric(vertical: rpx(14)),
          decoration: const BoxDecoration(
            border: Border(
                bottom: BorderSide(color: BrandColors.border, width: 0.5)),
          ),
          child: Row(
            children: [
              Container(
                width: rpx(16),
                height: rpx(16),
                decoration: BoxDecoration(
                    color: kPhaseColor[key] ?? BrandColors.primary,
                    shape: BoxShape.circle),
              ),
              SizedBox(width: rpx(16)),
              Expanded(
                child: Text(kPhaseFullLabel[key] ?? ps.label,
                    style: TextStyle(
                        fontSize: rpx(28), color: BrandColors.textPrimary)),
              ),
              if (ps.isWeakest)
                Container(
                  margin: EdgeInsets.only(right: rpx(16)),
                  padding: EdgeInsets.symmetric(
                      horizontal: rpx(14), vertical: rpx(4)),
                  decoration: BoxDecoration(
                    color: BrandColors.error.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(rpx(8)),
                  ),
                  child: Text('最需改进',
                      style: TextStyle(
                          fontSize: rpx(20), color: BrandColors.error)),
                ),
              Text('${ps.score}',
                  style: TextStyle(
                      fontSize: rpx(32),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
            ],
          ),
        ),
      );

  // -------------------- 问题诊断 --------------------
  List<Widget> _issuesSection(AnalysisReport r) {
    final order = {'high': 0, 'medium': 1, 'low': 2};
    final confident = r.issues
        .where((i) => i.confidenceTier != 'hidden')
        .toList()
      ..sort((a, b) =>
          (order[a.severity] ?? 9).compareTo(order[b.severity] ?? 9));
    final hidden =
        r.issues.where((i) => i.confidenceTier == 'hidden').toList();
    final primary = confident.isNotEmpty ? confident.first : null;
    final rest =
        primary == null ? confident : confident.where((i) => i != primary).toList();

    return [
      if (primary != null && !_isSample) ...[
        SizedBox(height: rpx(32)),
        _primaryFocus(r, primary),
      ],
      SizedBox(height: rpx(32)),
      _sectionCard(
        title: primary != null ? '其他问题' : '问题诊断',
        hint: '共 ${confident.length} 项',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (confident.isEmpty && hidden.isEmpty)
              Text(
                (r.overallScore ?? 100) < 65
                    ? '综合分偏低，但未命中典型错误模式，参考下方训练建议或问 AI 教练。'
                    : '🎉 这一杆没有明显问题，继续保持！',
                style: TextStyle(
                    fontSize: rpx(26),
                    height: 1.6,
                    color: BrandColors.textSecondary),
              )
            else if (rest.isEmpty)
              Text('其他问题不多，先把上面的「本周主攻」练扎实即可。',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary))
            else
              ...rest.map((i) => _issueCard(r, i)),
            if (hidden.isNotEmpty) _hiddenIssues(hidden),
          ],
        ),
      ),
    ];
  }

  Widget _primaryFocus(AnalysisReport r, AnalysisIssue issue) {
    final rec = r.recommendations.isEmpty
        ? null
        : r.recommendations.firstWhere(
            (x) => x.targetIssue == issue.type,
            orElse: () => r.recommendations.first,
          );
    final drill = rec != null ? getDrillDetail(rec.drillId) : null;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(rpx(32)),
      decoration: BoxDecoration(
        gradient: BrandColors.gradientHero,
        borderRadius: BorderRadius.circular(Radii.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('本周主攻',
              style: TextStyle(
                  fontSize: rpx(24),
                  color: BrandColors.onPrimaryMuted,
                  letterSpacing: 2)),
          SizedBox(height: rpx(12)),
          Row(
            children: [
              Expanded(
                child: Text(issue.name,
                    style: TextStyle(
                        fontSize: rpx(38),
                        fontWeight: FontWeight.w800,
                        color: BrandColors.onPrimary)),
              ),
              _severityTag(issue.severity),
            ],
          ),
          SizedBox(height: rpx(12)),
          Text(issue.description,
              style: TextStyle(
                  fontSize: rpx(26),
                  height: 1.6,
                  color: BrandColors.onPrimaryMuted)),
          if (drill != null) ...[
            SizedBox(height: rpx(12)),
            Text('推荐练习：${drill.name}',
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.onPrimary)),
          ],
          if (!_isSample) ...[
            SizedBox(height: rpx(24)),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _syncing ? null : _syncPlan,
                style: ElevatedButton.styleFrom(
                  backgroundColor: BrandColors.gold,
                  foregroundColor: Colors.black,
                ),
                child: _syncing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('去练这个动作'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _issueCard(AnalysisReport r, AnalysisIssue issue) {
    final leaning = issue.confidenceTier == 'leaning';
    final img = issue.keyFrameUrl?.isNotEmpty == true
        ? issue.keyFrameUrl!
        : (r.thumbnailUrl ?? '');
    return Container(
      width: double.infinity,
      margin: EdgeInsets.only(bottom: rpx(16)),
      padding: EdgeInsets.all(rpx(24)),
      decoration: BoxDecoration(
        color: BrandColors.bgPage,
        borderRadius: BorderRadius.circular(Radii.md),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                    '${leaning ? '可能存在·' : ''}${issue.name}',
                    style: TextStyle(
                        fontSize: rpx(30),
                        fontWeight: FontWeight.w700,
                        color: BrandColors.textPrimary)),
              ),
              _severityTag(issue.severity),
            ],
          ),
          if (img.isNotEmpty) ...[
            SizedBox(height: rpx(16)),
            ClipRRect(
              borderRadius: BorderRadius.circular(rpx(12)),
              child: CachedNetworkImage(
                imageUrl: img,
                height: rpx(280),
                width: double.infinity,
                fit: BoxFit.cover,
                errorWidget: (_, _, _) => const SizedBox.shrink(),
              ),
            ),
          ],
          SizedBox(height: rpx(12)),
          Text(issue.description,
              style: TextStyle(
                  fontSize: rpx(26),
                  height: 1.6,
                  color: BrandColors.textSecondary)),
          if (issue.keyFrameTimestamp != null && _video != null) ...[
            SizedBox(height: rpx(12)),
            GestureDetector(
              onTap: () => _seekTo(issue.keyFrameTimestamp!),
              child: Text(
                  '👆 跳转到 ${issue.keyFrameTimestamp!.toStringAsFixed(1)}s 关键帧',
                  style: TextStyle(
                      fontSize: rpx(24),
                      color: BrandColors.primary,
                      fontWeight: FontWeight.w600)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _hiddenIssues(List<AnalysisIssue> hidden) => Padding(
        padding: EdgeInsets.only(top: rpx(8)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              onTap: () => setState(() => _showHidden = !_showHidden),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('AI 不太确定（${hidden.length} 项）',
                      style: TextStyle(
                          fontSize: rpx(26), color: BrandColors.textSecondary)),
                  Text(_showHidden ? '收起 ▴' : '展开 ▾',
                      style: TextStyle(
                          fontSize: rpx(24), color: BrandColors.primary)),
                ],
              ),
            ),
            if (_showHidden) ...[
              SizedBox(height: rpx(12)),
              Text('以下诊断置信度较低，可能受画质 / 机位影响，仅供参考。',
                  style: TextStyle(
                      fontSize: rpx(22), color: BrandColors.textTertiary)),
              SizedBox(height: rpx(12)),
              ...hidden.map((i) => Padding(
                    padding: EdgeInsets.only(bottom: rpx(12)),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _severityTag(i.severity),
                        SizedBox(width: rpx(16)),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(i.name,
                                  style: TextStyle(
                                      fontSize: rpx(26),
                                      fontWeight: FontWeight.w600,
                                      color: BrandColors.textPrimary)),
                              Text(i.description,
                                  style: TextStyle(
                                      fontSize: rpx(24),
                                      color: BrandColors.textSecondary)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      );

  Widget _severityTag(String severity) {
    final color = switch (severity) {
      'high' => BrandColors.error,
      'low' => BrandColors.success,
      _ => BrandColors.warning,
    };
    return Container(
      padding: EdgeInsets.symmetric(horizontal: rpx(14), vertical: rpx(4)),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(rpx(8)),
      ),
      child: Text(kSeverityLabel[severity] ?? severity,
          style: TextStyle(fontSize: rpx(20), color: color)),
    );
  }

  // -------------------- 训练建议 --------------------
  List<Widget> _recommendationsSection(AnalysisReport r) {
    if (r.recommendations.isEmpty) return [];
    return [
      SizedBox(height: rpx(32)),
      _sectionCard(
        title: '训练建议',
        hint: '共 ${r.recommendations.length} 个动作',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!_isSample) ...[
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _syncing ? null : _syncPlan,
                  child: _syncing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('一键加入本周训练计划'),
                ),
              ),
              SizedBox(height: rpx(8)),
              Text('将根据本次问题自动追加当周任务（幂等，不重复）',
                  style: TextStyle(
                      fontSize: rpx(22), color: BrandColors.textTertiary)),
              SizedBox(height: rpx(16)),
            ],
            ...r.recommendations.map((rec) => _drillCard(getDrillDetail(rec.drillId))),
          ],
        ),
      ),
    ];
  }

  Widget _drillCard(DrillDetail d) => Container(
        width: double.infinity,
        margin: EdgeInsets.only(bottom: rpx(16)),
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: BrandColors.bgPage,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: BrandColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(d.name,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w700,
                          color: BrandColors.textPrimary)),
                ),
                Container(
                  padding: EdgeInsets.symmetric(
                      horizontal: rpx(14), vertical: rpx(4)),
                  decoration: BoxDecoration(
                    color: BrandColors.primaryTint,
                    borderRadius: BorderRadius.circular(rpx(8)),
                  ),
                  child: Text(d.difficulty,
                      style: TextStyle(
                          fontSize: rpx(20), color: BrandColors.primary)),
                ),
              ],
            ),
            SizedBox(height: rpx(12)),
            Text(d.description,
                style: TextStyle(
                    fontSize: rpx(26),
                    height: 1.5,
                    color: BrandColors.textSecondary)),
            SizedBox(height: rpx(12)),
            Wrap(
              spacing: rpx(24),
              runSpacing: rpx(8),
              children: [
                _metaChip('⏱ ${d.durationMinutes} 分钟'),
                _metaChip(
                    '🔄 ${d.sets} 组${d.reps != null ? ' × ${d.reps}' : ''}'),
                if (d.equipment.isNotEmpty)
                  _metaChip('🎒 ${d.equipment.join('、')}'),
              ],
            ),
            SizedBox(height: rpx(12)),
            for (var i = 0; i < d.steps.length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: rpx(8)),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: rpx(36),
                      height: rpx(36),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: BrandColors.primaryTint,
                        shape: BoxShape.circle,
                      ),
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
          ],
        ),
      );

  // -------------------- 底部动作 --------------------
  Widget _footer(AnalysisReport r) => Column(
        children: [
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _askCoach,
                  icon: const Icon(Icons.chat_bubble_outline, size: 18),
                  label: const Text('问 AI 教练'),
                ),
              ),
            ],
          ),
          SizedBox(height: rpx(16)),
          Row(
            children: [
              Expanded(
                child: ElevatedButton(
                  onPressed: _shootAgain,
                  child: const Text('再拍一段'),
                ),
              ),
              SizedBox(width: rpx(20)),
              Expanded(
                child: OutlinedButton(
                  onPressed: () =>
                      Navigator.of(context).popUntil((r) => r.isFirst),
                  child: const Text('返回首页'),
                ),
              ),
            ],
          ),
        ],
      );

  // -------------------- 通用 --------------------
  Widget _sectionCard(
          {required String title, String? hint, required Widget child}) =>
      Container(
        width: double.infinity,
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
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(title,
                    style: TextStyle(
                        fontSize: rpx(34),
                        fontWeight: FontWeight.w700,
                        color: BrandColors.textPrimary)),
                if (hint != null)
                  Text(hint,
                      style: TextStyle(
                          fontSize: rpx(24),
                          color: BrandColors.textTertiary)),
              ],
            ),
            SizedBox(height: rpx(20)),
            child,
          ],
        ),
      );

  // -------------------- 动作 --------------------
  Future<void> _syncPlan() async {
    if (_isSample) return;
    setState(() => _syncing = true);
    try {
      await context.read<TrainingRepository>().addFromAnalysis(widget.analysisId);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已同步到本周训练计划')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('同步失败，请稍后再试')));
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  void _shootAgain() {
    Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const CapturePage()));
  }

  void _askCoach() {
    Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => CoachPage(
              prefill: '这次我的挥杆，需要重点改什么？',
              contextAnalysisId: _isSample ? null : widget.analysisId,
            )));
  }
}
