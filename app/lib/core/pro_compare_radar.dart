import '../data/models/analysis.dart';
import '../data/models/content.dart';
import 'swing_constants.dart';

/// 对照 client/src/utils/proCompareRadar.ts

class ProPhaseCompareRow {
  final String key;
  final String label;
  final num? userScore;
  final num? proScore;
  final num? delta;
  final bool proIsReference;

  const ProPhaseCompareRow({
    required this.key,
    required this.label,
    this.userScore,
    this.proScore,
    this.delta,
    this.proIsReference = false,
  });
}

double _clampScore(num value) {
  final v = value.toDouble();
  if (v <= 10) return v.clamp(0, 10) * 10;
  if (v > 100) return (v / 10).clamp(0, 100);
  return v.clamp(0, 100);
}

Map<String, num?> deriveProPhaseScores(ProSwingClip clip) {
  final snap = clip.featuresSnapshot;
  final num? fallback = clip.overallScore;
  final out = <String, num?>{};
  for (final key in kPhaseOrder) {
    final raw = snap[key];
    if (raw is num) {
      out[key] = _clampScore(raw);
    } else {
      out[key] = fallback;
    }
  }
  return out;
}

bool proScoresAreReferenceOnly(ProSwingClip clip) {
  final snap = clip.featuresSnapshot;
  return !kPhaseOrder.any((key) => snap[key] is num);
}

List<({String key, String label, double score})> buildUserRadarAxes(
    AnalysisReport report) {
  if (report.phaseScores.isEmpty) return const [];
  return [
    for (final key in kPhaseOrder)
      (
        key: key,
        label: kPhaseLabel[key] ?? key,
        score: (report.phaseScores[key]?.score ?? 0).toDouble(),
      ),
  ];
}

List<({String key, String label, double score})> buildProRadarAxes(
  ProSwingClip clip,
  List<({String key, String label, double score})> userAxes,
) {
  final phaseScores = deriveProPhaseScores(clip);
  return [
    for (final axis in userAxes)
      (
        key: axis.key,
        label: axis.label,
        score: (phaseScores[axis.key] ?? 0).toDouble(),
      ),
  ];
}

List<ProPhaseCompareRow> buildProPhaseCompareRows(
  AnalysisReport report,
  ProSwingClip clip,
) {
  final proScores = deriveProPhaseScores(clip);
  final referenceOnly = proScoresAreReferenceOnly(clip);
  final rows = <ProPhaseCompareRow>[];
  for (final key in kPhaseOrder) {
    final userScore = report.phaseScores[key]?.score;
    final proScore = proScores[key];
    rows.add(ProPhaseCompareRow(
      key: key,
      label: kPhaseLabel[key] ?? key,
      userScore: userScore,
      proScore: proScore,
      delta: (userScore != null && proScore != null)
          ? userScore - proScore
          : null,
      proIsReference: referenceOnly,
    ));
  }
  return rows;
}
