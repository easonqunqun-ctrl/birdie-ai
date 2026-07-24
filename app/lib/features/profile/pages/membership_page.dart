import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api_client.dart';
import '../../../data/repositories/payment_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';

/// 会员中心：对照 client membership — 套餐列表 + mock 开通。
class MembershipPage extends StatefulWidget {
  const MembershipPage({super.key});

  @override
  State<MembershipPage> createState() => _MembershipPageState();
}

class _MembershipPageState extends State<MembershipPage> {
  static const _benefits = <(String, String, String)>[
    ('挥杆视频分析', '每月 3 次', '无限次'),
    ('AI 教练对话', '每天 5 轮', '无限次'),
    ('本周训练计划', '仅查看', '完整个性化'),
    ('进步曲线', '锁定', '完整历史与折线'),
    ('历史报告对比', '基础', '并排对比 + 晒进步'),
  ];

  PaymentRepository? _pay;
  List<PlanOption> _plans = const [];
  String? _selected;
  bool _loadingPlans = true;
  bool _buying = false;
  bool _plansRequested = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _pay ??= PaymentRepository(context.read<ApiClient>());
    if (!_plansRequested) {
      _plansRequested = true;
      _loadPlans();
    }
  }

  Future<void> _loadPlans() async {
    final pay = _pay;
    if (pay == null) return;
    try {
      final plans = await pay.listPlans();
      if (!mounted) return;
      setState(() {
        _plans = plans;
        _selected = plans.isNotEmpty ? plans.first.planType : null;
        _loadingPlans = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingPlans = false);
    }
  }

  Future<void> _buy() async {
    final plan = _selected;
    final pay = _pay;
    if (plan == null || _buying || pay == null) return;
    setState(() => _buying = true);
    try {
      final order = await pay.createOrder(plan);
      if (order.mockMode) {
        await pay.mockConfirm(order.orderId);
        if (!mounted) return;
        await context.read<AuthController>().refresh();
        if (!mounted) return;
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('开通成功（模拟支付）')));
      } else {
        if (!mounted) return;
        await _guideWeappPay();
      }
    } catch (e) {
      if (!mounted) return;
      final msg = describeRequestFailure(e).toastTitle;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } finally {
      if (mounted) setState(() => _buying = false);
    }
  }

  /// App 内 IAP / 微信 App 支付未上线：引导去微信小程序开通（与 docs/18 边界一致）。
  Future<void> _guideWeappPay() async {
    const tip =
        '正式支付请在微信小程序「领翼golf」会员中心完成。App 内目前仅支持联调模拟支付。';
    final open = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('去小程序开通'),
        content: const Text(tip),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('复制说明'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('尝试打开微信'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    if (open == false) {
      await Clipboard.setData(const ClipboardData(text: tip));
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已复制开通说明')));
      return;
    }
    if (open == true) {
      final uri = Uri.parse('weixin://');
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('未检测到微信，请手动打开小程序开通')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthController>().user;
    final isMember = user?.isMember == true;
    final typeLabel = switch (user?.membershipType) {
      'yearly' || 'annual' => '年度会员',
      'monthly' => '月度会员',
      _ => '会员',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('会员中心')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          Container(
            padding: EdgeInsets.all(rpx(40)),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFC9A227), Color(0xFF7A5F10)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(Radii.lg),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(isMember ? '👑 $typeLabel · 还剩 ${user?.membershipDaysRemaining ?? 0} 天' : '🎯 免费用户',
                    style: TextStyle(
                        fontSize: rpx(36),
                        fontWeight: FontWeight.w800,
                        color: Colors.white)),
                SizedBox(height: rpx(12)),
                Text(
                  isMember ? '感谢支持，尽情享受全部会员权益' : '解锁无限次挥杆分析与 AI 教练对话',
                  style: TextStyle(fontSize: rpx(28), color: Colors.white70),
                ),
              ],
            ),
          ),
          SizedBox(height: rpx(32)),
          _benefitTable(),
          if (!isMember) ...[
            SizedBox(height: rpx(32)),
            Text('选择套餐',
                style: TextStyle(
                    fontSize: rpx(32),
                    fontWeight: FontWeight.w700,
                    color: BrandColors.primary)),
            SizedBox(height: rpx(16)),
            if (_loadingPlans)
              const Center(child: CircularProgressIndicator())
            else if (_plans.isEmpty)
              Text('暂无可用套餐',
                  style: TextStyle(
                      fontSize: rpx(26), color: BrandColors.textSecondary))
            else
              ..._plans.map(_planTile),
            SizedBox(height: rpx(32)),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _buying || _selected == null ? null : _buy,
                style: ElevatedButton.styleFrom(
                    padding: EdgeInsets.symmetric(vertical: rpx(24))),
                child: Text(_buying ? '开通中…' : '立即开通'),
              ),
            ),
            SizedBox(height: rpx(16)),
            TextButton(
              onPressed: _guideWeappPay,
              child: Text('正式支付请用小程序开通',
                  style: TextStyle(
                      fontSize: rpx(24), color: BrandColors.textTertiary)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _planTile(PlanOption p) {
    final selected = _selected == p.planType;
    return GestureDetector(
      onTap: () => setState(() => _selected = p.planType),
      child: Container(
        margin: EdgeInsets.only(bottom: rpx(12)),
        padding: EdgeInsets.all(rpx(24)),
        decoration: BoxDecoration(
          color: selected ? BrandColors.goldSoft : BrandColors.bgCard,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(
              color: selected ? BrandColors.gold : BrandColors.border,
              width: selected ? 2 : 1),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(p.name,
                      style: TextStyle(
                          fontSize: rpx(30),
                          fontWeight: FontWeight.w700,
                          color: BrandColors.textPrimary)),
                  if (p.hint != null)
                    Text(p.hint!,
                        style: TextStyle(
                            fontSize: rpx(24),
                            color: BrandColors.textTertiary)),
                ],
              ),
            ),
            Text(p.amountYuanDisplay,
                style: TextStyle(
                    fontSize: rpx(32),
                    fontWeight: FontWeight.w800,
                    color: BrandColors.goldDark)),
          ],
        ),
      ),
    );
  }

  Widget _benefitTable() {
    return Container(
      decoration: BoxDecoration(
        color: BrandColors.bgCard,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: BrandColors.border),
      ),
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.all(rpx(24)),
            child: Row(
              children: [
                Expanded(
                    child: Text('权益',
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary))),
                SizedBox(
                    width: rpx(140),
                    child: Text('免费',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.textSecondary))),
                SizedBox(
                    width: rpx(160),
                    child: Text('会员',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: rpx(26),
                            color: BrandColors.goldDark))),
              ],
            ),
          ),
          for (final b in _benefits)
            Padding(
              padding: EdgeInsets.fromLTRB(rpx(24), 0, rpx(24), rpx(20)),
              child: Row(
                children: [
                  Expanded(
                      child: Text(b.$1,
                          style: TextStyle(
                              fontSize: rpx(26),
                              color: BrandColors.textPrimary))),
                  SizedBox(
                      width: rpx(140),
                      child: Text(b.$2,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(24),
                              color: BrandColors.textTertiary))),
                  SizedBox(
                      width: rpx(160),
                      child: Text(b.$3,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: rpx(24),
                              fontWeight: FontWeight.w600,
                              color: BrandColors.primary))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
