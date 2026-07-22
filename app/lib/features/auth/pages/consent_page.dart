import 'package:flutter/material.dart';

import '../../../core/storage.dart';
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

  static const _bullets = [
    '微信 OpenID：用于账号登录与标识（由微信授权获取，我们无法单独获取到你的微信号）。',
    '挥杆视频：仅在你主动拍摄/选择后上传，用于 AI 分析并生成报告。',
    '对话内容：用于 AI 教练问答；会通过国内合规 LLM 通道生成回复。',
  ];

  Future<void> _agree() async {
    if (!_agreed) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先勾选协议')),
      );
      return;
    }
    await AppStorage.instance.setAgreedTerms(AppStorage.currentTermsVersion);
    widget.onAgree();
  }

  void _reject() {
    setState(() => _rejected = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('不同意将无法使用本产品')),
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
                      Text('欢迎使用领翼golf',
                          style: TextStyle(
                              fontSize: rpx(50),
                              fontWeight: FontWeight.w700,
                              color: BrandColors.primary)),
                      SizedBox(height: rpx(12)),
                      Text('你的随身高尔夫智能教练',
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
          Text('在开始之前',
              style: TextStyle(
                  fontSize: rpx(36),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.primary)),
          SizedBox(height: rpx(16)),
          Text('我们非常重视你的个人信息保护。使用本产品，我们需要收集：',
              style: TextStyle(
                  fontSize: rpx(30),
                  height: 1.5,
                  color: BrandColors.textSecondary)),
          SizedBox(height: rpx(16)),
          ..._bullets.map((t) => Padding(
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
            '所有数据均存储在中国境内服务器，采用加密传输与存储。你可在「我的」页面随时查看、删除或注销账号。',
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
            child: Text('我已阅读并同意',
                style: TextStyle(
                    fontSize: rpx(30), color: BrandColors.textSecondary)),
          ),
          _link('《用户服务协议》', LegalKind.terms),
          Text('与',
              style: TextStyle(
                  fontSize: rpx(30), color: BrandColors.textSecondary)),
          _link('《隐私政策》', LegalKind.privacy),
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
              child: Text('同意并继续',
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
              child: Text('暂不同意',
                  style: TextStyle(
                      fontSize: rpx(32), color: BrandColors.textTertiary)),
            ),
          ),
        ),
        if (_rejected)
          Padding(
            padding: EdgeInsets.only(top: rpx(24)),
            child: Text('若暂不同意，请退出。你可以随时重新进入并选择同意。',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: rpx(28), color: BrandColors.warning)),
          ),
      ],
    );
  }
}
