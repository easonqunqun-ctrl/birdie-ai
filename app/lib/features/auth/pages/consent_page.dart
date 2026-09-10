import 'package:flutter/material.dart';

import '../../../core/storage.dart';
import '../../../l10n/l10n.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/brand_logo.dart';
import '../../legal/pages/legal_page.dart';

/// 首启合规页：对照 client/src/pages/consent/index.rn.tsx，视觉 1:1。
class ConsentPage extends StatefulWidget {
  const ConsentPage({super.key, required this.onAgree});
  final VoidCallback onAgree;

  @override
  State<ConsentPage> createState() => _ConsentPageState();
}

class _ConsentPageState extends State<ConsentPage> {
  bool _agreed = false;
  bool _rejected = false;

  List<String> _bullets(AppLocalizations l10n) => [
        l10n.consentBulletApple,
        l10n.consentBulletVideo,
        l10n.consentBulletChat,
      ];

  Future<void> _agree() async {
    if (!_agreed) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.l10n.agreeFirst)),
      );
      return;
    }
    await AppStorage.instance.setAgreedTerms(AppStorage.currentTermsVersion);
    widget.onAgree();
  }

  void _reject() {
    setState(() => _rejected = true);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.l10n.disagreeCannotUse)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.of(context).padding;
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: BrandColors.gradientAuthAtmosphere,
        ),
        child: Padding(
          padding: EdgeInsets.only(
            top: inset.top + rpx(48),
            bottom: inset.bottom + rpx(32),
            left: rpx(48),
            right: rpx(48),
          ),
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(height: rpx(20)),
                      const BrandLogo(size: 100),
                      SizedBox(height: rpx(20)),
                      Text(context.l10n.consentWelcome,
                          style: TextStyle(
                              fontSize: rpx(50),
                              fontWeight: FontWeight.w700,
                              color: BrandColors.primary)),
                      SizedBox(height: rpx(12)),
                      Text(context.l10n.tagline,
                          style: TextStyle(
                              fontSize: rpx(32),
                              color: BrandColors.textSecondary)),
                      SizedBox(height: rpx(36)),
                      _card(),
                    ],
                  ),
                ),
              ),
              _bottom(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _card() {
    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(32)),
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(rpx(32)),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(context.l10n.consentBefore,
              style: TextStyle(
                  fontSize: rpx(36),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.primary)),
          SizedBox(height: rpx(16)),
          Text(context.l10n.consentIntro,
              style: TextStyle(
                  fontSize: rpx(30),
                  height: 1.5,
                  color: BrandColors.textSecondary)),
          SizedBox(height: rpx(16)),
          ..._bullets(context.l10n).map((t) => Padding(
                padding: EdgeInsets.only(bottom: rpx(12)),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: rpx(10),
                      height: rpx(10),
                      margin: EdgeInsets.only(top: rpx(16), right: rpx(14)),
                      decoration: const BoxDecoration(
                          color: BrandColors.gold, shape: BoxShape.circle),
                    ),
                    Expanded(
                      child: Text(t,
                          style: TextStyle(
                              fontSize: rpx(30),
                              height: 1.5,
                              color: BrandColors.textPrimary)),
                    ),
                  ],
                ),
              )),
          SizedBox(height: rpx(4)),
          Text(
            context.l10n.consentStorage,
            style: TextStyle(
                fontSize: rpx(30),
                height: 1.5,
                color: BrandColors.textSecondary),
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
                  ? Icon(Icons.check,
                      size: rpx(28), color: BrandColors.onPrimary)
                  : null,
            ),
          ),
          GestureDetector(
            onTap: () => setState(() => _agreed = !_agreed),
            child: Text(context.l10n.agreeReadPrefix,
                style: TextStyle(
                    fontSize: rpx(30), color: BrandColors.textSecondary)),
          ),
          _link(context.l10n.userAgreement, LegalKind.terms),
          Text(context.l10n.withWord,
              style: TextStyle(
                  fontSize: rpx(30), color: BrandColors.textSecondary)),
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
                fontSize: rpx(30),
                fontWeight: FontWeight.w600,
                color: BrandColors.primary)),
      );

  Widget _bottom() {
    return Column(
      children: [
        _agreement(),
        SizedBox(height: rpx(20)),
        GestureDetector(
          onTap: _agreed ? _agree : null,
          child: Opacity(
            opacity: _agreed ? 1 : 0.45,
            child: Container(
              width: double.infinity,
              height: rpx(96),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                  color: BrandColors.primary,
                  borderRadius: BorderRadius.circular(Radii.md)),
              child: Text(context.l10n.agreeContinue,
                  style: TextStyle(
                      fontSize: rpx(36),
                      fontWeight: FontWeight.w600,
                      color: BrandColors.onPrimary)),
            ),
          ),
        ),
        SizedBox(height: rpx(20)),
        GestureDetector(
          onTap: _reject,
          child: SizedBox(
            height: rpx(64),
            child: Center(
              child: Text(context.l10n.notNow,
                  style: TextStyle(
                      fontSize: rpx(32), color: BrandColors.textTertiary)),
            ),
          ),
        ),
        if (_rejected)
          Padding(
            padding: EdgeInsets.only(top: rpx(24)),
            child: Text(context.l10n.consentDisagreeExit,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: rpx(28), color: BrandColors.warning)),
          ),
      ],
    );
  }
}
