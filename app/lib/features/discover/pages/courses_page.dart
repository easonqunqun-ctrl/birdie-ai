import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../data/models/content.dart';
import '../../../data/repositories/content_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 课程学习：对照 client/src/pages/courses。列表只读（学习流在后续版本）。
class CoursesPage extends StatefulWidget {
  const CoursesPage({super.key});

  @override
  State<CoursesPage> createState() => _CoursesPageState();
}

class _CoursesPageState extends State<CoursesPage> {
  late Future<List<Course>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<ContentRepository>().listCourses();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('课程学习')),
      body: FutureBuilder<List<Course>>(
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
            return const _Empty(text: '课程即将上线，敬请期待');
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

  Widget _card(Course c) => Container(
        padding: EdgeInsets.all(rpx(28)),
        decoration: BoxDecoration(
          color: BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.lg),
          border: Border.all(color: BrandColors.border),
        ),
        child: Row(
          children: [
            Container(
              width: rpx(88),
              height: rpx(88),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: BrandColors.primaryTint,
                borderRadius: BorderRadius.circular(Radii.md),
              ),
              child: Text('L${c.stage}',
                  style: TextStyle(
                      fontSize: rpx(32),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.primary)),
            ),
            SizedBox(width: rpx(24)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(c.title,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.textPrimary)),
                  if (c.subtitle != null) ...[
                    SizedBox(height: rpx(8)),
                    Text(c.subtitle!,
                        style: TextStyle(
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary)),
                  ],
                ],
              ),
            ),
            if (c.isMemberOnly)
              Icon(Icons.lock_outline, color: BrandColors.gold, size: rpx(36)),
          ],
        ),
      );
}

class _Empty extends StatelessWidget {
  const _Empty({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.school_outlined,
              size: rpx(96), color: BrandColors.textTertiary),
          SizedBox(height: rpx(16)),
          Text(text,
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.textSecondary)),
        ],
      ),
    );
  }
}
