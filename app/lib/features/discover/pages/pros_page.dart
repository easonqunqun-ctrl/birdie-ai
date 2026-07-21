import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:provider/provider.dart';

import '../../../data/models/content.dart';
import '../../../data/repositories/content_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 高手对比：对照 client/src/pages/pros。球手列表只读。
class ProsPage extends StatefulWidget {
  const ProsPage({super.key});

  @override
  State<ProsPage> createState() => _ProsPageState();
}

class _ProsPageState extends State<ProsPage> {
  late Future<List<ProPlayer>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<ContentRepository>().listPros();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('高手对比')),
      body: FutureBuilder<List<ProPlayer>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(
                child: CircularProgressIndicator(
                    valueColor:
                        AlwaysStoppedAnimation<Color>(BrandColors.primary)));
          }
          final list = snap.data ?? const [];
          if (snap.hasError || list.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.emoji_events_outlined,
                      size: rpx(96), color: BrandColors.textTertiary),
                  SizedBox(height: rpx(16)),
                  Text('球手对比库即将上线',
                      style: TextStyle(
                          fontSize: rpx(28),
                          color: BrandColors.textSecondary)),
                ],
              ),
            );
          }
          return ListView.separated(
            padding: EdgeInsets.all(rpx(32)),
            itemCount: list.length,
            separatorBuilder: (_, _) => SizedBox(height: rpx(20)),
            itemBuilder: (_, i) => _card(list[i]),
          );
        },
      ),
    );
  }

  Widget _card(ProPlayer p) => Container(
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Row(
          children: [
            CircleAvatar(
              radius: rpx(48),
              backgroundColor: BrandColors.primaryTint,
              backgroundImage: p.avatarUrl != null
                  ? CachedNetworkImageProvider(p.avatarUrl!)
                  : null,
              child: p.avatarUrl == null
                  ? Text(p.name.isNotEmpty ? p.name.characters.first : '?',
                      style: const TextStyle(color: BrandColors.primary))
                  : null,
            ),
            SizedBox(width: rpx(24)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(p.name,
                      style: TextStyle(
                          fontSize: rpx(32),
                          fontWeight: FontWeight.w700,
                          color: BrandColors.textPrimary)),
                  if (p.shortBio != null) ...[
                    SizedBox(height: rpx(8)),
                    Text(p.shortBio!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary)),
                  ],
                ],
              ),
            ),
          ],
        ),
      );
}
