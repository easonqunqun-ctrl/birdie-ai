import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/api_client.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/brand_logo.dart';
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

  static const _features = [
    ('📹', 'AI 挥杆分析，30 秒出报告'),
    ('💬', '24 小时 AI 教练在线问答'),
    ('📈', '个性化训练方案'),
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
      _toast('请先勾选协议');
      return;
    }
    if (_loading) return;
    setState(() => _loading = true);
    try {
      final invite = _inviteCtl.text.trim().toUpperCase();
      await context
          .read<AuthController>()
          .loginWithWechat(inviteCode: invite.isEmpty ? null : invite);
      // 成功：AppGate 会自动切到 onboarding / 首页
    } catch (e) {
      final msg = describeRequestFailure(e).toastTitle;
      _toast(msg);
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.of(context).padding;
    return Scaffold(
      backgroundColor: BrandColors.bgPage,
      body: Padding(
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
                  Text('领翼golf',
                      style: TextStyle(
                          fontSize: rpx(54),
                          fontWeight: FontWeight.w700,
                          color: BrandColors.primary)),
                  SizedBox(height: rpx(8)),
                  Text('你的随身高尔夫智能教练',
                      style: TextStyle(
                          fontSize: rpx(30),
                          color: BrandColors.textSecondary)),
                  SizedBox(height: rpx(48)),
                  ..._features.map(_featureRow),
                  SizedBox(height: rpx(28)),
                ],
              ),
            ),
            _agreement(),
            SizedBox(height: rpx(20)),
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
                    child: Text(_loading ? '登录中...' : '微信一键登录',
                        style: TextStyle(
                            fontSize: rpx(36),
                            fontWeight: FontWeight.w600,
                            color: BrandColors.onPrimary)),
                  ),
                ),
              ),
            ),
            SizedBox(height: rpx(16)),
            _invite(),
          ],
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
            child: Text('我已阅读并同意',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.textSecondary)),
          ),
          _link('《用户服务协议》', LegalKind.terms),
          Text('和',
              style: TextStyle(
                  fontSize: rpx(28), color: BrandColors.textSecondary)),
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
                fontSize: rpx(28),
                fontWeight: FontWeight.w600,
                color: BrandColors.primary)),
      );

  Widget _invite() {
    if (!_showInvite) {
      return GestureDetector(
        onTap: () => setState(() => _showInvite = true),
        child: Text('有邀请码？点击填写（可选）',
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
            hintText: '请输入 8 位邀请码',
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
        Text('使用邀请码：你与邀请人本月各 +1 次分析',
            style: TextStyle(
                fontSize: rpx(28), color: BrandColors.textSecondary)),
      ],
    );
  }
}
