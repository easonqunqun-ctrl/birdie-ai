import '../data/models/training.dart';

/// 训练打卡月历布局：对照 client/src/utils/practiceCalendarLayout.ts。

class PracticeCalendarCell {
  final String dateKey;
  final int day;
  final int count;
  final bool isToday;
  final bool inMonth;

  const PracticeCalendarCell({
    required this.dateKey,
    required this.day,
    required this.count,
    required this.isToday,
    required this.inMonth,
  });
}

class PracticeCalendarGrid {
  final String monthKey;
  final List<List<PracticeCalendarCell>> weeks;
  final int monthTotal;

  const PracticeCalendarGrid({
    required this.monthKey,
    required this.weeks,
    required this.monthTotal,
  });
}

const practiceCalendarWeekdayLabels = ['一', '二', '三', '四', '五', '六', '日'];

({int year, int month})? parseMonthKey(String monthKey) {
  final m = RegExp(r'^(\d{4})-(\d{2})$').firstMatch(monthKey);
  if (m == null) return null;
  final year = int.tryParse(m.group(1)!);
  final month = int.tryParse(m.group(2)!);
  if (year == null || month == null || month < 1 || month > 12) return null;
  return (year: year, month: month);
}

String localDateKey([DateTime? d]) {
  final x = d ?? DateTime.now();
  return '${x.year}-${_two(x.month)}-${_two(x.day)}';
}

String monthKeyNow([DateTime? d]) {
  final x = d ?? DateTime.now();
  return '${x.year}-${_two(x.month)}';
}

String shiftMonthKey(String monthKey, int delta) {
  final parsed = parseMonthKey(monthKey);
  if (parsed == null) return monthKeyNow();
  var year = parsed.year;
  var month = parsed.month + delta;
  while (month < 1) {
    month += 12;
    year -= 1;
  }
  while (month > 12) {
    month -= 12;
    year += 1;
  }
  return '$year-${_two(month)}';
}

Map<String, int> aggregatePracticeCounts(Iterable<PracticeLogItem> logs) {
  final counts = <String, int>{};
  for (final log in logs) {
    final raw = log.practiceDate ?? '';
    final key = raw.length >= 10 ? raw.substring(0, 10) : '';
    if (key.isEmpty) continue;
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}

PracticeCalendarGrid buildPracticeCalendarGrid(
  String monthKey,
  Map<String, int> counts, [
  String? todayKey,
]) {
  final today = todayKey ?? localDateKey();
  final parsed = parseMonthKey(monthKey);
  if (parsed == null) {
    return PracticeCalendarGrid(monthKey: monthKey, weeks: const [], monthTotal: 0);
  }
  final year = parsed.year;
  final month = parsed.month;
  final first = DateTime(year, month, 1);
  final lastDay = DateTime(year, month + 1, 0).day;
  final firstWeekday = (first.weekday + 6) % 7; // Mon=0

  var monthTotal = 0;
  for (var day = 1; day <= lastDay; day++) {
    final key = '$year-${_two(month)}-${_two(day)}';
    monthTotal += counts[key] ?? 0;
  }

  final cells = <PracticeCalendarCell>[];
  for (var i = 0; i < firstWeekday; i++) {
    cells.add(const PracticeCalendarCell(
        dateKey: '', day: 0, count: 0, isToday: false, inMonth: false));
  }
  for (var day = 1; day <= lastDay; day++) {
    final key = '$year-${_two(month)}-${_two(day)}';
    cells.add(PracticeCalendarCell(
      dateKey: key,
      day: day,
      count: counts[key] ?? 0,
      isToday: key == today,
      inMonth: true,
    ));
  }
  while (cells.length % 7 != 0) {
    cells.add(const PracticeCalendarCell(
        dateKey: '', day: 0, count: 0, isToday: false, inMonth: false));
  }
  while (cells.length < 42) {
    cells.add(const PracticeCalendarCell(
        dateKey: '', day: 0, count: 0, isToday: false, inMonth: false));
  }

  final weeks = <List<PracticeCalendarCell>>[];
  for (var i = 0; i < cells.length; i += 7) {
    weeks.add(cells.sublist(i, i + 7));
  }
  return PracticeCalendarGrid(
      monthKey: monthKey, weeks: weeks, monthTotal: monthTotal);
}

String formatMonthTitle(String monthKey) {
  final parsed = parseMonthKey(monthKey);
  if (parsed == null) return monthKey;
  return '${parsed.year}年${parsed.month}月';
}

String _two(int n) => n.toString().padLeft(2, '0');
