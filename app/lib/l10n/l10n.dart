import 'package:flutter/material.dart';

import 'app_localizations.dart';

export 'app_localizations.dart';

extension AppL10nX on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
}
