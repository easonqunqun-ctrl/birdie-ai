import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:video_player/video_player.dart';

import '../../../data/models/content.dart';
import '../../../data/repositories/content_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 对照 client/src/pages/pros/detail：球手镜头列表 + 可播示范视频。
class ProPlayerDetailPage extends StatefulWidget {
  const ProPlayerDetailPage({super.key, required this.player});

  final ProPlayer player;

  @override
  State<ProPlayerDetailPage> createState() => _ProPlayerDetailPageState();
}

class _ProPlayerDetailPageState extends State<ProPlayerDetailPage> {
  late Future<List<ProSwingClip>> _future;
  final Map<String, VideoPlayerController> _players = {};
  final Set<String> _ready = {};

  @override
  void initState() {
    super.initState();
    _future = context.read<ContentRepository>().listPlayerClips(widget.player.id);
  }

  @override
  void dispose() {
    for (final c in _players.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _ensurePlayer(ProSwingClip clip) async {
    if (clip.videoUrl.isEmpty || _players.containsKey(clip.id)) return;
    final ctl = VideoPlayerController.networkUrl(Uri.parse(clip.videoUrl));
    _players[clip.id] = ctl;
    try {
      await ctl.initialize();
      await ctl.setLooping(true);
      if (mounted) setState(() => _ready.add(clip.id));
    } catch (_) {/* 网络失败时卡片仍显示文案 */}
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.player;
    return Scaffold(
      appBar: AppBar(title: Text(p.name)),
      body: FutureBuilder<List<ProSwingClip>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
              child: Text(
                '镜头加载失败',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary),
              ),
            );
          }
          final clips = snap.data ?? const [];
          return ListView(
            padding: EdgeInsets.all(rpx(32)),
            children: [
              if (p.shortBio != null && p.shortBio!.isNotEmpty) ...[
                Text(p.shortBio!,
                    style: TextStyle(
                        fontSize: rpx(26),
                        height: 1.45,
                        color: BrandColors.textSecondary)),
                SizedBox(height: rpx(24)),
              ],
              if (clips.isEmpty)
                Text('该球手暂无已发布镜头',
                    style: TextStyle(
                        fontSize: rpx(28), color: BrandColors.textSecondary))
              else
                ...clips.map(_clipCard),
            ],
          );
        },
      ),
    );
  }

  Widget _clipCard(ProSwingClip clip) {
    WidgetsBinding.instance.addPostFrameCallback((_) => _ensurePlayer(clip));
    final ctl = _players[clip.id];
    final ready = _ready.contains(clip.id);
    final angle = clip.cameraAngle == 'face_on' ? '正面' : '侧线';
    return Container(
      margin: EdgeInsets.only(bottom: rpx(24)),
      padding: EdgeInsets.all(rpx(20)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 16 / 9,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(Radii.md),
              child: Container(
                color: Colors.black,
                child: ready && ctl != null
                    ? Stack(
                        alignment: Alignment.center,
                        children: [
                          VideoPlayer(ctl),
                          IconButton(
                            onPressed: () {
                              setState(() {
                                if (ctl.value.isPlaying) {
                                  ctl.pause();
                                } else {
                                  ctl.play();
                                }
                              });
                            },
                            icon: Icon(
                              ctl.value.isPlaying
                                  ? Icons.pause_circle_outline
                                  : Icons.play_circle_outline,
                              color: Colors.white,
                              size: rpx(72),
                            ),
                          ),
                        ],
                      )
                    : Center(
                        child: clip.videoUrl.isEmpty
                            ? Text('暂无视频',
                                style: TextStyle(
                                    color: Colors.white70, fontSize: rpx(26)))
                            : const CircularProgressIndicator(
                                color: Colors.white),
                      ),
              ),
            ),
          ),
          SizedBox(height: rpx(16)),
          Text('${clip.clubType} · $angle',
              style: TextStyle(
                  fontSize: rpx(30),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.textPrimary)),
          if (clip.overallScore != null)
            Text('职业综合分 ${clip.overallScore}',
                style: TextStyle(
                    fontSize: rpx(24), color: BrandColors.goldDark)),
          if (clip.sourceCredit.isNotEmpty)
            Text('来源：${clip.sourceCredit}',
                style: TextStyle(
                    fontSize: rpx(22), color: BrandColors.textTertiary)),
        ],
      ),
    );
  }
}
