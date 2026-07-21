import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/analysis_options.dart';
import '../../../data/models/training.dart';
import '../../../data/repositories/user_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 我的装备：装备清单只读展示（增删改在后续里程碑）。对照 profile/clubs。
class ClubsPage extends StatefulWidget {
  const ClubsPage({super.key});

  @override
  State<ClubsPage> createState() => _ClubsPageState();
}

class _ClubsPageState extends State<ClubsPage> {
  late Future<List<UserClub>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<UserRepository>().listClubs();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('我的装备')),
      body: FutureBuilder<List<UserClub>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(
                child: CircularProgressIndicator(
                    valueColor:
                        AlwaysStoppedAnimation<Color>(BrandColors.primary)));
          }
          final clubs = snap.data ?? const [];
          if (snap.hasError || clubs.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.golf_course,
                      size: rpx(96), color: BrandColors.textTertiary),
                  SizedBox(height: rpx(16)),
                  Text('暂无装备，添加你的常用球杆',
                      style: TextStyle(
                          fontSize: rpx(28),
                          color: BrandColors.textSecondary)),
                ],
              ),
            );
          }
          return ListView.separated(
            padding: EdgeInsets.all(rpx(32)),
            itemCount: clubs.length,
            separatorBuilder: (_, _) => SizedBox(height: rpx(16)),
            itemBuilder: (_, i) => _clubCard(clubs[i]),
          );
        },
      ),
    );
  }

  Widget _clubCard(UserClub c) => Container(
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Row(
          children: [
            const Icon(Icons.sports_golf, color: BrandColors.primary),
            SizedBox(width: rpx(20)),
            Expanded(
              child: Text(c.nickname?.isNotEmpty == true
                  ? c.nickname!
                  : (clubTypeLabels[c.clubType] ?? c.clubType),
                  style: TextStyle(
                      fontSize: rpx(30), color: BrandColors.textPrimary)),
            ),
            Text(c.selfYardageM != null ? '${c.selfYardageM}m' : '未填码数',
                style: TextStyle(
                    fontSize: rpx(28),
                    color: c.selfYardageM != null
                        ? BrandColors.textSecondary
                        : BrandColors.textTertiary)),
          ],
        ),
      );
}
