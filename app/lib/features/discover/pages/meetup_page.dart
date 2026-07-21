import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../data/models/content.dart';
import '../../../data/repositories/content_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 约球 / 挑战赛：对照 client/src/pages/meetup。活动列表只读。
class MeetupPage extends StatefulWidget {
  const MeetupPage({super.key});

  @override
  State<MeetupPage> createState() => _MeetupPageState();
}

class _MeetupPageState extends State<MeetupPage> {
  late Future<List<MeetupEvent>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<ContentRepository>().listMeetups();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('约球 / 挑战赛')),
      body: FutureBuilder<List<MeetupEvent>>(
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
                  Icon(Icons.groups_outlined,
                      size: rpx(96), color: BrandColors.textTertiary),
                  SizedBox(height: rpx(16)),
                  Text('暂无进行中的活动',
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

  Widget _card(MeetupEvent e) => Container(
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
                Expanded(
                  child: Text(e.title,
                      style: TextStyle(
                          fontSize: rpx(32),
                          fontWeight: FontWeight.w700,
                          color: BrandColors.textPrimary)),
                ),
                if (e.templateLabel != null)
                  Container(
                    padding: EdgeInsets.symmetric(
                        horizontal: rpx(16), vertical: rpx(6)),
                    decoration: BoxDecoration(
                      color: BrandColors.accentMintDim,
                      borderRadius: BorderRadius.circular(rpx(8)),
                    ),
                    child: Text(e.templateLabel!,
                        style: TextStyle(
                            fontSize: rpx(22), color: BrandColors.success)),
                  ),
              ],
            ),
            if (e.description != null) ...[
              SizedBox(height: rpx(12)),
              Text(e.description!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary)),
            ],
            SizedBox(height: rpx(16)),
            Row(
              children: [
                Icon(Icons.people_outline,
                    size: rpx(30), color: BrandColors.textTertiary),
                SizedBox(width: rpx(8)),
                Text(
                  '${e.participantCount}${e.capacity != null ? ' / ${e.capacity}' : ''} 人',
                  style: TextStyle(
                      fontSize: rpx(24), color: BrandColors.textSecondary),
                ),
              ],
            ),
          ],
        ),
      );
}
