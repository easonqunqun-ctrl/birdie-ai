import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/storage.dart';
import '../theme/brand_colors.dart';
import '../widgets/brand_logo.dart';
import '../features/auth/auth_controller.dart';
import '../features/auth/pages/consent_page.dart';
import '../features/onboarding/pages/onboarding_page.dart';
import 'tab_shell.dart';

/// 启动分流：consent →（已登录且未引导）onboarding → TabShell。
/// 未登录也可进 TabShell 访客浏览（对齐小程序审核：禁止强制登录）。
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
    } else if (auth.isLoggedIn &&
        (auth.user == null || !auth.user!.onboardingCompleted)) {
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
            SizedBox(height: 16),
            CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(BrandColors.primary),
            ),
          ],
        ),
      ),
    );
  }
}
