import 'package:flutter/material.dart';

import '../theme/brand_colors.dart';
import 'storage.dart';
import '../l10n/l10n.dart';

/// App Store 5.1.1 / 5.1.2：向第三方 AI 发送数据前须明示内容、接收方并征得同意。
class AiDataConsent {
  AiDataConsent._();

  /// 返回 true 表示用户已同意（或此前已同意）。
  static Future<bool> ensure(BuildContext context, {required AiConsentKind kind}) async {
    final s = AppStorage.instance;
    if (s.hasAiDataConsent) return true;
    final l10n = context.l10n;

    final detail = switch (kind) {
      AiConsentKind.swingAnalysis => l10n.aiConsentSwing,
      AiConsentKind.coachChat => l10n.aiConsentChat,
    };

    final ok = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.aiConsentTitle),
        content: SingleChildScrollView(
          child: Text(
            '$detail\n\n'
            '${l10n.aiConsentReceivers}\n'
            '· ${l10n.aiConsentOurCloud}\n'
            '· ${l10n.aiConsentProvider}\n\n'
            '${l10n.aiConsentPurpose}',
            style: const TextStyle(height: 1.45, color: BrandColors.textPrimary),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(l10n.disagree),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(l10n.agreeContinue),
          ),
        ],
      ),
    );

    if (ok == true) {
      await s.setAiDataConsent(true);
      return true;
    }
    return false;
  }
}

enum AiConsentKind { swingAnalysis, coachChat }
