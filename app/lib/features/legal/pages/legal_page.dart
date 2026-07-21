import 'package:flutter/material.dart';
import '../../../theme/brand_colors.dart';

enum LegalKind { terms, privacy }

/// 用户协议 / 隐私政策。M0 先放占位骨架，P4 再补全文本（对齐 pages/legal/*）。
class LegalPage extends StatelessWidget {
  const LegalPage({super.key, required this.kind});
  final LegalKind kind;

  String get _title =>
      kind == LegalKind.terms ? '用户服务协议' : '隐私政策';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_title)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('领翼golf · $_title',
                style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: BrandColors.primary)),
            const SizedBox(height: 16),
            const Text(
              '（正式全文将在 P4 里程碑从小程序 pages/legal 同步。此处为占位，'
              '确保合规页链接可跳转、闭环可跑通。）',
              style: TextStyle(
                  fontSize: 14, height: 1.7, color: BrandColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
