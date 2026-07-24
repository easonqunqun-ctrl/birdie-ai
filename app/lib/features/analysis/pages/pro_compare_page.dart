import 'package:cached_network_image/cached_network_image.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../../../core/analysis_options.dart';
import '../../../core/api_client.dart';
import '../../../core/pro_compare_radar.dart';
import '../../../data/models/analysis.dart';
import '../../../data/models/content.dart';
import '../../../data/repositories/content_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../analysis_controller.dart';

/// 对照 client/src/pages/analysis/pro-compare.tsx
class ProComparePage extends StatefulWidget {
  const ProComparePage({
    super.key,
    required this.analysisId,
    this.clipId,
  });

  final String analysisId;
  final String? clipId;

  @override
  State<ProComparePage> createState() => _ProComparePageState();
}

class _ProComparePageState extends State<ProComparePage> {
  bool _loading = true;
  String? _error;
  AnalysisReport? _report;
  ProMatchItem? _match;

  VideoPlayerController? _userVideo;
  VideoPlayerController? _proVideo;
  bool _userReady = false;
  bool _proReady = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _userVideo?.dispose();
    _proVideo?.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (widget.analysisId == 'sample') {
      setState(() {
        _error = '示例报告不支持职业对比';
        _loading = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    final analysis = context.read<AnalysisController>();
    final contentRepo = ContentRepository(context.read<ApiClient>());
    try {
      final report = await analysis.loadReport(widget.analysisId);
      if (!mounted) return;
      if (report.status != 'completed') {
        setState(() {
          _error = '仅已完成分析可与职业镜头对比';
          _loading = false;
        });
        return;
      }
      final matchResult =
          await contentRepo.matchForAnalysis(widget.analysisId, limit: 5);
      if (!mounted) return;
      final clipId = widget.clipId?.trim() ?? '';
      ProMatchItem? picked;
      if (clipId.isNotEmpty) {
        for (final m in matchResult.matches) {
          if (m.clip.id == clipId) {
            picked = m;
            break;
          }
        }
      }
      picked ??= matchResult.matches.isEmpty ? null : matchResult.matches.first;
      if (picked == null) {
        setState(() {
          _error = '暂无匹配的职业镜头，请稍后再试';
          _loading = false;
        });
        return;
      }
      setState(() {
        _report = report;
        _match = picked;
        _loading = false;
      });
      _initVideos(report, picked);
    } on ApiException catch (e) {
      if (!mounted) return;
      final msg = e.status == 404
          ? '球手对比库尚未开放'
          : describeRequestFailure(e).toastTitle;
      setState(() {
        _error = msg;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = describeRequestFailure(e).toastTitle;
        _loading = false;
      });
    }
  }

  Future<void> _initVideos(AnalysisReport report, ProMatchItem match) async {
    final userSrc = (report.skeletonVideoUrl?.isNotEmpty == true)
        ? report.skeletonVideoUrl!
        : report.videoUrl;
    if (userSrc.isNotEmpty) {
      final ctl = VideoPlayerController.networkUrl(Uri.parse(userSrc));
      _userVideo = ctl;
      try {
        await ctl.initialize();
        await ctl.setLooping(true);
        if (mounted) setState(() => _userReady = true);
      } catch (_) {/* ignore */}
    }
    final proSrc = match.clip.videoUrl;
    if (proSrc.isNotEmpty) {
      final ctl = VideoPlayerController.networkUrl(Uri.parse(proSrc));
      _proVideo = ctl;
      try {
        await ctl.initialize();
        await ctl.setLooping(true);
        if (mounted) setState(() => _proReady = true);
      } catch (_) {/* ignore */}
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('职业对比')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _errorBody(_error!)
              : _body(),
    );
  }

  Widget _errorBody(String msg) => Center(
        child: Padding(
          padding: EdgeInsets.all(rpx(48)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(msg,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(28), color: BrandColors.textSecondary)),
              SizedBox(height: rpx(24)),
              OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('返回')),
            ],
          ),
        ),
      );

  Widget _body() {
    final report = _report!;
    final match = _match!;
    final club = clubTypeLabels[report.clubType] ?? report.clubType;
    final angle = cameraAngleLabels[report.cameraAngle] ?? report.cameraAngle;
    final userAxes = buildUserRadarAxes(report);
    final proAxes = buildProRadarAxes(match.clip, userAxes);
    final phaseRows = buildProPhaseCompareRows(report, match.clip);
    final refOnly = proScoresAreReferenceOnly(match.clip);

    return ListView(
      padding: EdgeInsets.all(rpx(32)),
      children: [
        Text('和职业球手并排对比',
            style: TextStyle(
                fontSize: rpx(36),
                fontWeight: FontWeight.w800,
                color: BrandColors.primary)),
        SizedBox(height: rpx(8)),
        Text(
          '匹配度 ${match.matchScore} · ${match.player.name}',
          style: TextStyle(fontSize: rpx(28), color: BrandColors.textSecondary),
        ),
        Text('$club · $angle',
            style:
                TextStyle(fontSize: rpx(24), color: BrandColors.textTertiary)),
        SizedBox(height: rpx(28)),
        Row(
          children: [
            Expanded(
              child: _scoreCol('你', report.overallScore),
            ),
            SizedBox(width: rpx(16)),
            Expanded(
              child: _scoreCol('职业', match.clip.overallScore, pro: true),
            ),
          ],
        ),
        SizedBox(height: rpx(28)),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _videoCol(
                label: '你的挥杆',
                ready: _userReady,
                controller: _userVideo,
                poster: report.thumbnailUrl,
              ),
            ),
            SizedBox(width: rpx(12)),
            Expanded(
              child: _videoCol(
                label: match.player.name,
                ready: _proReady,
                controller: _proVideo,
                poster: match.clip.thumbnailUrl,
              ),
            ),
          ],
        ),
        if (match.clip.sourceCredit.isNotEmpty) ...[
          SizedBox(height: rpx(12)),
          Text('来源：${match.clip.sourceCredit}',
              style: TextStyle(
                  fontSize: rpx(22), color: BrandColors.textTertiary)),
        ],
        if (userAxes.isNotEmpty && proAxes.isNotEmpty) ...[
          SizedBox(height: rpx(32)),
          _section(
            title: '六维雷达叠加',
            hint: refOnly ? '职业镜头暂无分阶段明细，虚线为综合分参考基线' : null,
            child: SizedBox(
              height: rpx(420),
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
                      text: index < userAxes.length
                          ? userAxes[index].label
                          : ''),
                  titleTextStyle: TextStyle(
                      fontSize: rpx(22), color: BrandColors.textSecondary),
                  dataSets: [
                    RadarDataSet(
                      fillColor: BrandColors.primary.withValues(alpha: 0.18),
                      borderColor: BrandColors.primary,
                      borderWidth: 2,
                      entryRadius: 3,
                      dataEntries: [
                        for (final a in userAxes) RadarEntry(value: a.score),
                      ],
                    ),
                    RadarDataSet(
                      fillColor: BrandColors.gold.withValues(alpha: 0.12),
                      borderColor: BrandColors.gold,
                      borderWidth: refOnly ? 1.5 : 2,
                      entryRadius: 3,
                      dataEntries: [
                        for (final a in proAxes) RadarEntry(value: a.score),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
        if (phaseRows.isNotEmpty) ...[
          SizedBox(height: rpx(32)),
          _section(
            title: '六维分差',
            child: Column(
              children: [
                _phaseHead(),
                for (final row in phaseRows) _phaseRow(row),
              ],
            ),
          ),
        ],
        SizedBox(height: rpx(32)),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('返回完整报告'),
          ),
        ),
        SizedBox(height: rpx(40)),
      ],
    );
  }

  Widget _scoreCol(String tag, num? score, {bool pro = false}) => Container(
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: pro ? BrandColors.goldSoft : BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(
              color: pro ? BrandColors.gold : BrandColors.border),
        ),
        child: Column(
          children: [
            Text(tag,
                style: TextStyle(
                    fontSize: rpx(24),
                    color: pro ? BrandColors.goldDark : BrandColors.textSecondary)),
            SizedBox(height: rpx(8)),
            Text(score?.round().toString() ?? '—',
                style: TextStyle(
                    fontSize: rpx(48),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.primary)),
          ],
        ),
      );

  Widget _videoCol({
    required String label,
    required bool ready,
    required VideoPlayerController? controller,
    String? poster,
  }) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: TextStyle(
                  fontSize: rpx(24),
                  fontWeight: FontWeight.w600,
                  color: BrandColors.textSecondary)),
          SizedBox(height: rpx(8)),
          AspectRatio(
            aspectRatio: 9 / 16,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(Radii.md),
              child: Container(
                color: Colors.black,
                child: ready && controller != null
                    ? Stack(
                        alignment: Alignment.center,
                        children: [
                          VideoPlayer(controller),
                          IconButton(
                            onPressed: () {
                              setState(() {
                                if (controller.value.isPlaying) {
                                  controller.pause();
                                } else {
                                  controller.play();
                                }
                              });
                            },
                            icon: Icon(
                              controller.value.isPlaying
                                  ? Icons.pause_circle_outline
                                  : Icons.play_circle_outline,
                              color: Colors.white,
                              size: rpx(56),
                            ),
                          ),
                        ],
                      )
                    : poster != null && poster.isNotEmpty
                        ? CachedNetworkImage(
                            imageUrl: poster, fit: BoxFit.cover)
                        : Center(
                            child: Text('暂无视频',
                                style: TextStyle(
                                    color: Colors.white54,
                                    fontSize: rpx(22))),
                          ),
              ),
            ),
          ),
        ],
      );

  Widget _section({
    required String title,
    String? hint,
    required Widget child,
  }) =>
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
            Text(title,
                style: TextStyle(
                    fontSize: rpx(32),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.textPrimary)),
            if (hint != null) ...[
              SizedBox(height: rpx(8)),
              Text(hint,
                  style: TextStyle(
                      fontSize: rpx(22), color: BrandColors.textTertiary)),
            ],
            SizedBox(height: rpx(16)),
            child,
          ],
        ),
      );

  Widget _phaseHead() => Padding(
        padding: EdgeInsets.only(bottom: rpx(8)),
        child: Row(
          children: [
            Expanded(
                flex: 2,
                child: Text('阶段',
                    style: TextStyle(
                        fontSize: rpx(22),
                        color: BrandColors.textTertiary))),
            Expanded(
                child: Text('你',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: rpx(22),
                        color: BrandColors.textTertiary))),
            Expanded(
                child: Text('职业',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: rpx(22),
                        color: BrandColors.textTertiary))),
            Expanded(
                child: Text('差值',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: rpx(22),
                        color: BrandColors.textTertiary))),
          ],
        ),
      );

  Widget _phaseRow(ProPhaseCompareRow row) {
    final d = row.delta;
    Color deltaColor = BrandColors.textSecondary;
    if (d != null && d > 0) deltaColor = BrandColors.accentMint;
    if (d != null && d < 0) deltaColor = BrandColors.error;
    final deltaText = d == null
        ? '—'
        : d == 0
            ? '0'
            : '${d > 0 ? '+' : ''}${d is int ? d : d.round()}';
    return Padding(
      padding: EdgeInsets.symmetric(vertical: rpx(10)),
      child: Row(
        children: [
          Expanded(
              flex: 2,
              child: Text(row.label,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textPrimary))),
          Expanded(
              child: Text('${row.userScore?.round() ?? '—'}',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textPrimary))),
          Expanded(
              child: Text('${row.proScore?.round() ?? '—'}',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textPrimary))),
          Expanded(
              child: Text(deltaText,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: rpx(26),
                      fontWeight: FontWeight.w600,
                      color: deltaColor))),
        ],
      ),
    );
  }
}
