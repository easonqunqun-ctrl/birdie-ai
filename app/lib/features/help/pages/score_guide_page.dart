import 'package:flutter/material.dart';

import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';

/// 分数说明：对照 client/src/pages/help/score-guide。
class ScoreGuidePage extends StatelessWidget {
  const ScoreGuidePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      appBar: AppBar(title: const Text('分数说明')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          Text('帮助您理解报告上的得分',
              style: TextStyle(
                  fontSize: rpx(26), color: BrandColors.textSecondary)),
          SizedBox(height: rpx(28)),
          _section('分数表示什么', [
            '在当期算法版本中，综合分与各维度分表示：在当前视频里软件能够看清的前提下，您的挥杆动作与领翼golf 采用的「结构化理想挥杆模型」之间的贴合程度，并综合若干可计算的几何与节奏特征。',
            '分数越高，表示与当前模型的一致性越好。更适合用于同一人在相近条件下多次拍摄的纵向对比，以及找出相对薄弱的维度；不必过度纠结单次绝对值。',
          ]),
          _section('分数不表示什么', [
            '不是世界排名，也不是对名人或选手的「强弱评判」。',
            '不能替代球场杆数、比赛成绩或教练的现场综合判断。',
            '在机位不佳、身体未完整入镜、光线过暗或挥杆被遮挡时，分数可能不稳定；建议按拍摄引导重新录制后再看报告。',
          ], bullets: true),
          _section('如何更好地使用分数', [
            '建议您在相近日期、相似拍摄条件下多拍几次，观察分数与诊断的变化趋势，往往比盯着单次分数更有参考价值。',
          ]),
          _section('其他常见问题', [
            '顶尖选手的视频分数看起来不高？许多职业球员有强烈的个人技术特点，在「标准模型」下可能出现看似偏低的分数，但这不代表其竞技水平弱于模型。',
            '和线下教练结论不一致？AI 主要从可见的几何与节奏信息给出参考；教练可能还会结合球路、策略与现场观察。若结论冲突，请以线下教练为准。',
          ]),
          SizedBox(height: rpx(24)),
          Text('如需更多帮助，可通过「我的」中的意见反馈联系我们。',
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.textTertiary)),
        ],
      ),
    );
  }

  Widget _section(String title, List<String> paras, {bool bullets = false}) {
    return Padding(
      padding: EdgeInsets.only(bottom: rpx(28)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  fontSize: rpx(32),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.primary)),
          SizedBox(height: rpx(12)),
          for (final p in paras)
            Padding(
              padding: EdgeInsets.only(bottom: rpx(10)),
              child: Text(bullets ? '· $p' : p,
                  style: TextStyle(
                      fontSize: rpx(28),
                      height: 1.55,
                      color: BrandColors.textSecondary)),
            ),
        ],
      ),
    );
  }
}
