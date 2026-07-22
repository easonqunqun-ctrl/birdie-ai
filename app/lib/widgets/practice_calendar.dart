import 'package:flutter/material.dart';

import '../core/practice_calendar_layout.dart';
import '../theme/brand_colors.dart';
import '../theme/dimens.dart';

/// 训练打卡月历：对照 client PracticeCalendar。
class PracticeCalendar extends StatelessWidget {
  const PracticeCalendar({
    super.key,
    required this.grid,
    this.onPrevMonth,
    this.onNextMonth,
    this.canGoNext = true,
    this.embedded = false,
  });

  final PracticeCalendarGrid grid;
  final VoidCallback? onPrevMonth;
  final VoidCallback? onNextMonth;
  final bool canGoNext;
  final bool embedded;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(rpx(embedded ? 8 : 24)),
      decoration: embedded
          ? null
          : BoxDecoration(
              color: BrandColors.bgCard,
              borderRadius: BorderRadius.circular(Radii.lg),
              border: Border.all(color: BrandColors.border),
            ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _nav('‹', onPrevMonth),
              Text(formatMonthTitle(grid.monthKey),
                  style: TextStyle(
                      fontSize: rpx(30),
                      fontWeight: FontWeight.w700,
                      color: BrandColors.textPrimary)),
              _nav('›', canGoNext ? onNextMonth : null, disabled: !canGoNext),
            ],
          ),
          SizedBox(height: rpx(16)),
          Row(
            children: [
              for (final w in practiceCalendarWeekdayLabels)
                Expanded(
                  child: Text(w,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: rpx(22),
                          color: BrandColors.textTertiary)),
                ),
            ],
          ),
          SizedBox(height: rpx(8)),
          for (final week in grid.weeks)
            Padding(
              padding: EdgeInsets.only(bottom: rpx(6)),
              child: Row(
                children: [
                  for (final cell in week) Expanded(child: _cell(cell)),
                ],
              ),
            ),
          SizedBox(height: rpx(8)),
          Text('本月打卡 ${grid.monthTotal} 次',
              style: TextStyle(
                  fontSize: rpx(24), color: BrandColors.textSecondary)),
        ],
      ),
    );
  }

  Widget _nav(String label, VoidCallback? onTap, {bool disabled = false}) {
    return GestureDetector(
      onTap: onTap,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: rpx(16), vertical: rpx(8)),
        child: Text(label,
            style: TextStyle(
                fontSize: rpx(40),
                color: disabled
                    ? BrandColors.textTertiary
                    : BrandColors.primary)),
      ),
    );
  }

  Widget _cell(PracticeCalendarCell cell) {
    if (!cell.inMonth) return SizedBox(height: rpx(64));
    final practiced = cell.count > 0;
    return Container(
      height: rpx(64),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: practiced
            ? BrandColors.accentMintDim
            : cell.isToday
                ? BrandColors.primaryTint
                : Colors.transparent,
        borderRadius: BorderRadius.circular(rpx(12)),
        border: cell.isToday
            ? Border.all(color: BrandColors.primary, width: 1)
            : null,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('${cell.day}',
              style: TextStyle(
                  fontSize: rpx(24),
                  fontWeight:
                      cell.isToday ? FontWeight.w700 : FontWeight.w500,
                  color: practiced
                      ? BrandColors.success
                      : BrandColors.textPrimary)),
          if (practiced)
            Text(cell.count > 1 ? '${cell.count}' : '·',
                style: TextStyle(
                    fontSize: rpx(18),
                    height: 1,
                    color: BrandColors.accentMint)),
        ],
      ),
    );
  }
}
