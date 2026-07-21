import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/storage.dart';
import '../theme/brand_colors.dart';
import '../widgets/brand_logo.dart';
import '../features/auth/auth_controller.dart';
import '../features/auth/pages/consent_page.dart';
import '../features/auth/pages/login_page.dart';
import '../features/onboarding/pages/onboarding_page.dart';
import 'tab_shell.dart';

/// 启动分流：consent → login → onboarding → 首页（TabShell）。
/// 依据 AuthController 状态与本地协议同意标记响应式切换，无需显式 Navigator。
class AppGate extends StatefulWidget {
  const AppGate({super.key});

  @override
  State<AppGate> createState() => _AppGateState();
}

class _AppGateState extends State<AppGate> {
  bool _agreed = AppStorage.instance.hasAgreedCurrentTerms();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();

    Widget child;
    if (!auth.initialized) {
      child = const _Splash();
    } else if (!_agreed) {
      child = ConsentPage(onAgree: () => setState(() => _agreed = true));
    } else if (!auth.isLoggedIn) {
      child = const LoginPage();
    } else if (auth.user == null || !auth.user!.onboardingCompleted) {
      child = const OnboardingPage();
    } else {
      child = const TabShell();
    }

    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: KeyedSubtree(key: ValueKey(child.runtimeType), child: child),
    );
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            BrandLogo(size: 96),
            SizedBox(height: 24),
            CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(BrandColors.primary),
            ),
          ],
        ),
      ),
    );
  }
}
