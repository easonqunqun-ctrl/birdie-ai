import 'dart:io';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import '../../../core/api_client.dart';
import '../../../core/apple_auth.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/brand_logo.dart';
import '../../../l10n/l10n.dart';
import '../auth_controller.dart';
import '../../legal/pages/legal_page.dart';

/// 登录页：对照 client/src/pages/login/index.rn.tsx，视觉 1:1。
/// 登录成功后由 AppGate 依据登录态/onboarding 自动分流。
class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool _agreed = false;
  bool _loading = false;
  bool _showInvite = false;
  final _inviteCtl = TextEditingController();

  List<(String, String)> _features(AppLocalizations l10n) => [
        ('📹', l10n.featureSwing),
        ('💬', l10n.featureCoach),
        ('📈', l10n.featurePlan),
      ];

  @override
  void dispose() {
    _inviteCtl.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _login() async {
    if (!_agreed) {
      _toast(context.l10n.agreeFirst);
      return;
    }
    if (_loading) return;
    setState(() => _loading = true);
    try {
      final invite = _inviteCtl.text.trim().toUpperCase();
      await context
          .read<AuthController>()
          .loginWithWechat(inviteCode: invite.isEmpty ? null : invite);
      // LoginPage 多为 push 叠在访客首页上；成功后必须 pop，否则会卡在「登录中」
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
    } catch (e) {
      final msg = describeRequestFailure(e).toastTitle;
      _toast(msg);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loginApple() async {
    if (!_agreed) {
      _toast(context.l10n.agreeFirst);
      return;
    }
    if (_loading) return;
    setState(() => _loading = true);
    try {
      final invite = _inviteCtl.text.trim().toUpperCase();
      await context
          .read<AuthController>()
          .loginWithApple(inviteCode: invite.isEmpty ? null : invite);
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
    } catch (e) {
      final msg = describeRequestFailure(e).toastTitle;
      _toast(msg);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final inset = MediaQuery.of(context).padding;
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: BrandColors.gradientAuthAtmosphere,
        ),
        child: Padding(
          padding: EdgeInsets.only(
            top: inset.top + rpx(56),
            bottom: inset.bottom + rpx(32),
            left: rpx(48),
            right: rpx(48),
          ),
          child: Column(
            children: [
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    const BrandLogo(size: 100),
                    SizedBox(height: rpx(16)),
                    Text(l10n.appName,
                        style: TextStyle(
                            fontSize: rpx(54),
                            fontWeight: FontWeight.w700,
                            color: BrandColors.primary)),
                    SizedBox(height: rpx(8)),
                    Text(l10n.tagline,
                        style: TextStyle(
                            fontSize: rpx(30),
                            color: BrandColors.textSecondary)),
                    SizedBox(height: rpx(48)),
                    ..._features(l10n).map(_featureRow),
                    SizedBox(height: rpx(28)),
                  ],
                ),
              ),
              _agreement(),
              SizedBox(height: rpx(20)),
              // iOS App Store：不得要求先安装微信才能登录（Guideline 4.2.3(i)）
              if (Platform.isIOS) ...[
                FutureBuilder<bool>(
                  future: AppleAuth.isAvailable,
                  builder: (context, snap) {
                    if (snap.data != true) {
                      return Text(
                        l10n.appleDeviceRequired,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: rpx(28),
                            color: BrandColors.textSecondary),
                      );
                    }
                    return SignInWithAppleButton(
                      onPressed: (!_agreed || _loading) ? () {} : _loginApple,
                      style: SignInWithAppleButtonStyle.black,
                      borderRadius: BorderRadius.circular(Radii.md),
                      height: rpx(88),
                    );
                  },
                ),
                SizedBox(height: rpx(12)),
                Text(l10n.appleLoginHint,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: rpx(24), color: BrandColors.textTertiary)),
              ] else ...[
                SizedBox(
                  width: double.infinity,
                  child: GestureDetector(
                    onTap: (!_agreed || _loading) ? null : _login,
                    child: Opacity(
                      opacity: (!_agreed || _loading) ? 0.45 : 1,
                      child: Container(
                        height: rpx(88),
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                            color: BrandColors.primary,
                            borderRadius: BorderRadius.circular(Radii.md)),
                        child: Text(_loading ? l10n.signingIn : l10n.wechatLogin,
                            style: TextStyle(
                                fontSize: rpx(36),
                                fontWeight: FontWeight.w600,
                                color: BrandColors.onPrimary)),
                      ),
                    ),
                  ),
                ),
              ],
              SizedBox(height: rpx(16)),
              // 审核：显著「取消/拒绝」——暂不登录可返回访客浏览
              GestureDetector(
                onTap: _loading
                    ? null
                    : () {
                        if (Navigator.of(context).canPop()) {
                          Navigator.of(context).pop();
                        }
                      },
                child: Container(
                  width: double.infinity,
                  height: rpx(80),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: BrandColors.bgCard,
                    borderRadius: BorderRadius.circular(Radii.md),
                    border: Border.all(color: BrandColors.border),
                  ),
                  child: Text(l10n.browseAsGuest,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w600,
                          color: BrandColors.primary)),
                ),
              ),
              SizedBox(height: rpx(16)),
              _invite(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _featureRow((String, String) f) {
    return Container(
      width: double.infinity,
      margin: EdgeInsets.only(bottom: rpx(16)),
      padding: EdgeInsets.symmetric(horizontal: rpx(24), vertical: rpx(20)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(rpx(24)),
        border: Border.all(color: BrandColors.border),
      ),
      child: Row(
        children: [
          Text(f.$1, style: TextStyle(fontSize: rpx(42))),
          SizedBox(width: rpx(20)),
          Expanded(
            child: Text(f.$2,
                style: TextStyle(
                    fontSize: rpx(32), color: BrandColors.textPrimary)),
          ),
        ],
      ),
    );
  }

  Widget _agreement() {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: rpx(8), vertical: rpx(12)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(rpx(24)),
      ),
      child: Wrap(
        alignment: WrapAlignment.center,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          GestureDetector(
            onTap: () => setState(() => _agreed = !_agreed),
            child: Container(
              width: rpx(44),
              height: rpx(44),
              margin: EdgeInsets.only(right: rpx(12)),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: _agreed ? BrandColors.primary : BrandColors.bgCard,
                shape: BoxShape.circle,
                border: Border.all(
                    color: _agreed
                        ? BrandColors.primary
                        : BrandColors.primarySoft,
                    width: 2),
              ),
              child: _agreed
                  ? Icon(Icons.check, size: rpx(28), color: BrandColors.onPrimary)
                  : null,
            ),
          ),
          GestureDetector(
            onTap: () => setState(() => _agreed = !_agreed),
            child: Text(context.l10n.agreeReadPrefix,
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
          ),
          _link(context.l10n.userAgreement, LegalKind.terms),
          Text(context.l10n.andWord,
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.textSecondary)),
          _link(context.l10n.privacyPolicy, LegalKind.privacy),
        ],
      ),
    );
  }

  Widget _link(String text, LegalKind kind) => GestureDetector(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => LegalPage(kind: kind)),
        ),
        child: Text(text,
            style: TextStyle(
                fontSize: rpx(28),
                fontWeight: FontWeight.w600,
                color: BrandColors.primary)),
      );

  Widget _invite() {
    if (!_showInvite) {
      return GestureDetector(
        onTap: () => setState(() => _showInvite = true),
        child: Text(context.l10n.inviteOptional,
            style: TextStyle(
                fontSize: rpx(28),
                color: BrandColors.primary,
                decoration: TextDecoration.underline)),
      );
    }
    return Column(
      children: [
        TextField(
          controller: _inviteCtl,
          maxLength: 8,
          textAlign: TextAlign.center,
          textCapitalization: TextCapitalization.characters,
          style: TextStyle(fontSize: rpx(34), letterSpacing: 4),
          decoration: InputDecoration(
            counterText: '',
            hintText: context.l10n.inviteHint,
            filled: true,
            fillColor: BrandColors.bgCard,
            contentPadding: EdgeInsets.symmetric(horizontal: rpx(24)),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(rpx(24)),
              borderSide: const BorderSide(color: BrandColors.border),
            ),
          ),
          onChanged: (v) {
            final up = v.toUpperCase();
            if (up != v) {
              _inviteCtl.value = _inviteCtl.value.copyWith(
                text: up,
                selection: TextSelection.collapsed(offset: up.length),
              );
            }
          },
        ),
        SizedBox(height: rpx(12)),
        Text(context.l10n.inviteBonus,
            style: TextStyle(
                fontSize: rpx(28), color: BrandColors.textSecondary)),
      ],
    );
  }
}
