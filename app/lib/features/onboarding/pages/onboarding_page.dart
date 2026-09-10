import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/api_client.dart';
import '../../../core/golf_options.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';
import '../../../l10n/l10n.dart';

/// 新用户引导：对照 client/src/pages/onboarding/index.tsx（v1 三步流）。
class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key});

  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  static const _totalSteps = 3;
  int _step = 1;
  String? _level;
  final _goals = <String>[];
  String? _freq;
  bool _submitting = false;

  bool get _canNext =>
      (_step == 1 && _level != null) ||
      (_step == 2 && _goals.isNotEmpty) ||
      (_step == 3 && _freq != null);

  void _toggleGoal(String g) {
    setState(() {
      if (_goals.contains(g)) {
        _goals.remove(g);
      } else if (_goals.length < maxGoals) {
        _goals.add(g);
      }
    });
  }

  void _toast(String msg) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _submit() async {
    if (_level == null || _freq == null || _goals.isEmpty) return;
    setState(() => _submitting = true);
    try {
      await context.read<AuthController>().completeOnboarding(
            golfLevel: _level!,
            primaryGoals: List.of(_goals),
            weeklyPracticeFrequency: _freq!,
          );
      // 完成：AppGate 自动切首页
    } catch (e) {
      _toast(describeRequestFailure(e).toastTitle);
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _skip() async {
    final auth = context.read<AuthController>();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(context.l10n.skipProfileTitle),
        content: Text(context.l10n.skipProfileBody),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(context.l10n.keepFilling)),
          TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(context.l10n.confirmSkip)),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _submitting = true);
    try {
      // 跳过：只把 onboarding 置位（对齐小程序「跳过」仅 PATCH onboarding_completed，不写档案）。
      await auth.updateProfile({'onboarding_completed': true});
    } catch (e) {
      _toast(describeRequestFailure(e).toastTitle);
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.of(context).padding;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: Padding(
        padding: EdgeInsets.only(
          top: inset.top + rpx(28),
          bottom: inset.bottom + rpx(48),
          left: rpx(40),
          right: rpx(40),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _header(),
            SizedBox(height: rpx(48)),
            Expanded(child: SingleChildScrollView(child: _stepBody())),
            _footer(),
          ],
        ),
      ),
    );
  }

  Widget _header() {
    return Row(
      children: [
        Expanded(
          child: Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(rpx(8)),
                  child: LinearProgressIndicator(
                    value: _step / _totalSteps,
                    minHeight: rpx(12),
                    backgroundColor: BrandColors.border,
                    valueColor: const AlwaysStoppedAnimation<Color>(
                        BrandColors.primary),
                  ),
                ),
              ),
              SizedBox(width: rpx(16)),
              Text('$_step / $_totalSteps',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary)),
            ],
          ),
        ),
        SizedBox(width: rpx(16)),
        GestureDetector(
          onTap: _submitting ? null : _skip,
          child: Text(_submitting ? context.l10n.skipping : context.l10n.skip,
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.textTertiary)),
        ),
      ],
    );
  }

  Widget _stepBody() {
    final l10n = context.l10n;
    switch (_step) {
      case 1:
        return _stepColumn(l10n.onboardingLevelQ, [
          for (final l in levels)
            _option(
                localizedLevel(l10n, l.value),
                _level == l.value,
                () => setState(() => _level = l.value),
                desc: localizedLevelDesc(l10n, l.value)),
        ]);
      case 2:
        return _stepColumn(l10n.onboardingGoalsQ(maxGoals), [
          for (final g in goals)
            _option(localizedGoal(l10n, g.value), _goals.contains(g.value),
                () => _toggleGoal(g.value)),
        ]);
      default:
        return _stepColumn(l10n.onboardingFreqQ, [
          for (final f in freqs)
            _option(localizedFreq(l10n, f.value), _freq == f.value,
                () => setState(() => _freq = f.value)),
        ]);
    }
  }

  Widget _stepColumn(String title, List<Widget> options) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: TextStyle(
                fontSize: rpx(44),
                fontWeight: FontWeight.w700,
                color: BrandColors.textPrimary)),
        SizedBox(height: rpx(32)),
        ...options,
      ],
    );
  }

  Widget _option(String label, bool active, VoidCallback onTap, {String? desc}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        margin: EdgeInsets.only(bottom: rpx(20)),
        padding: EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(28)),
        decoration: BoxDecoration(
          color: active ? BrandColors.primaryTint : BrandColors.bgCard,
          borderRadius: BorderRadius.circular(rpx(24)),
          border: Border.all(
              color: active ? BrandColors.primary : BrandColors.border,
              width: active ? 2 : 1),
        ),
        child: Row(
          children: [
            Container(
              width: rpx(8),
              height: rpx(48),
              margin: EdgeInsets.only(right: rpx(20)),
              decoration: BoxDecoration(
                color: active ? BrandColors.primary : Colors.transparent,
                borderRadius: BorderRadius.circular(rpx(4)),
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: TextStyle(
                          fontSize: rpx(34),
                          fontWeight: FontWeight.w600,
                          color: active
                              ? BrandColors.primary
                              : BrandColors.textPrimary)),
                  if (desc != null) ...[
                    SizedBox(height: rpx(6)),
                    Text(desc,
                        style: TextStyle(
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _footer() {
    return Row(
      children: [
        if (_step > 1)
          Expanded(
            child: GestureDetector(
              onTap: _submitting ? null : () => setState(() => _step--),
              child: Container(
                height: rpx(88),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: BrandColors.bgCard,
                  borderRadius: BorderRadius.circular(Radii.md),
                  border: Border.all(color: BrandColors.border),
                ),
                child: Text(context.l10n.previousStep,
                    style: TextStyle(
                        fontSize: rpx(34), color: BrandColors.textSecondary)),
              ),
            ),
          ),
        if (_step > 1) SizedBox(width: rpx(20)),
        Expanded(
          child: GestureDetector(
            onTap: () {
              if (!_canNext) return;
              if (_step < _totalSteps) {
                setState(() => _step++);
              } else {
                _submit();
              }
            },
            child: Opacity(
              opacity: _canNext && !_submitting ? 1 : 0.5,
              child: Container(
                height: rpx(88),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                    color: BrandColors.primary,
                    borderRadius: BorderRadius.circular(Radii.md)),
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                                BrandColors.onPrimary)))
                    : Text(_step < _totalSteps
                        ? context.l10n.nextStep
                        : context.l10n.done,
                        style: TextStyle(
                            fontSize: rpx(34),
                            fontWeight: FontWeight.w600,
                            color: BrandColors.onPrimary)),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
