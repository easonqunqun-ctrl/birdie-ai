import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

class ProgressChartPoint {
  final DateTime at;
  final double score;
  const ProgressChartPoint({required this.at, required this.score});
}

/// 进步折线：对照 client ProgressLineChart（用 fl_chart）。
class ProgressLineChart extends StatelessWidget {
  const ProgressLineChart({
    super.key,
    required this.points,
    this.height,
  });

  final List<ProgressChartPoint> points;
  final double? height;

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) {
      return Container(
        height: height ?? rpx(280),
        alignment: Alignment.center,
        child: Text('至少 2 次分析后显示进步曲线',
            style: TextStyle(
                fontSize: rpx(26), color: BrandColors.textSecondary)),
      );
    }
    final spots = <FlSpot>[];
    for (var i = 0; i < points.length; i++) {
      spots.add(FlSpot(i.toDouble(), points[i].score));
    }
    final minY = spots.map((s) => s.y).reduce((a, b) => a < b ? a : b);
    final maxY = spots.map((s) => s.y).reduce((a, b) => a > b ? a : b);
    final pad = ((maxY - minY) * 0.15).clamp(2.0, 10.0);

    return SizedBox(
      height: height ?? rpx(280),
      child: LineChart(
        LineChartData(
          minY: (minY - pad).clamp(0, 100),
          maxY: (maxY + pad).clamp(0, 100),
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            getDrawingHorizontalLine: (_) => FlLine(
              color: BrandColors.border,
              strokeWidth: 1,
            ),
          ),
          titlesData: FlTitlesData(
            topTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: rpx(40),
                getTitlesWidget: (v, _) => Text(v.toInt().toString(),
                    style: TextStyle(
                        fontSize: rpx(20), color: BrandColors.textTertiary)),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: (points.length / 4).clamp(1, 10).toDouble(),
                getTitlesWidget: (v, _) {
                  final i = v.round();
                  if (i < 0 || i >= points.length) return const SizedBox.shrink();
                  final d = points[i].at;
                  return Padding(
                    padding: EdgeInsets.only(top: rpx(8)),
                    child: Text('${d.month}/${d.day}',
                        style: TextStyle(
                            fontSize: rpx(18),
                            color: BrandColors.textTertiary)),
                  );
                },
              ),
            ),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              color: BrandColors.primary,
              barWidth: 3,
              dotData: FlDotData(
                show: true,
                getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                  radius: 3.5,
                  color: BrandColors.primary,
                  strokeWidth: 0,
                ),
              ),
              belowBarData: BarAreaData(
                show: true,
                color: BrandColors.primary.withValues(alpha: 0.08),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
