import '../data/models/analysis.dart';

/// 短于此时长（秒）的候选视为噪声，不进入选段页。
const kMinSwingCandidateDurationSec = 0.6;

({List<SwingCandidate> candidates, int defaultIndex}) sanitizeSwingCandidates(
  List<SwingCandidate> candidates,
  int defaultSelectedIndex,
) {
  final filtered = candidates
      .where((c) => c.durationSec >= kMinSwingCandidateDurationSec)
      .toList();
  if (filtered.isEmpty) {
    return (candidates: candidates, defaultIndex: defaultSelectedIndex);
  }

  var nextDefault = 0;
  if (defaultSelectedIndex >= 0 && defaultSelectedIndex < candidates.length) {
    final preferred = candidates[defaultSelectedIndex];
    final idx = filtered.indexWhere((c) =>
        c.startFrame == preferred.startFrame &&
        c.endFrame == preferred.endFrame);
    if (idx >= 0) {
      nextDefault = idx;
    } else {
      final formal = filtered.indexWhere((c) => !c.isPractice);
      nextDefault = formal >= 0 ? formal : 0;
    }
  } else {
    final formal = filtered.indexWhere((c) => !c.isPractice);
    nextDefault = formal >= 0 ? formal : 0;
  }
  return (candidates: filtered, defaultIndex: nextDefault);
}
