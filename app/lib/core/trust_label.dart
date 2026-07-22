/// 可信度档位：对照 client/src/utils/trustLabel.ts。

enum TrustTier { high, medium, low }

const kHighConfidenceThreshold = 0.75;
const kLowConfidenceThreshold = 0.5;

TrustTier resolveTrustTier(num? confidence) {
  final value = (confidence ?? 1.0).toDouble();
  if (value >= kHighConfidenceThreshold) return TrustTier.high;
  if (value >= kLowConfidenceThreshold) return TrustTier.medium;
  return TrustTier.low;
}

bool shouldRecommendRetake(num? confidence) {
  final value = (confidence ?? 1.0).toDouble();
  return value < kLowConfidenceThreshold;
}

({String title, String hint}) trustTierCopy(TrustTier tier) => switch (tier) {
      TrustTier.high => (
          title: 'AI 高可信',
          hint: '画质、机位、姿态识别均良好，本次分析结果可信。',
        ),
      TrustTier.medium => (
          title: 'AI 中等可信，可参考',
          hint: '部分信号偏弱，建议在更好的光线/机位下再拍一段对比。',
        ),
      TrustTier.low => (
          title: 'AI 难以做出可靠分析',
          hint: '画质或机位影响识别，建议按提示重拍后再分析。',
        ),
    };
