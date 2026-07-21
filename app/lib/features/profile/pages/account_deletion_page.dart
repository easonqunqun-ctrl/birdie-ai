import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../data/repositories/user_repository.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../auth/auth_controller.dart';

/// 注销账号：对照 profile/account-deletion。输入 DELETE 确认 + 已排期可撤销。
class AccountDeletionPage extends StatefulWidget {
  const AccountDeletionPage({super.key});

  @override
  State<AccountDeletionPage> createState() => _AccountDeletionPageState();
}

class _AccountDeletionPageState extends State<AccountDeletionPage> {
  static const _confirmText = 'DELETE';
  final _ctl = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_ctl.text.trim() != _confirmText) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('请输入大写 $_confirmText 以确认')));
      return;
    }
    final auth = context.read<AuthController>();
    final repo = context.read<UserRepository>();
    final sure = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('最后确认'),
        content: const Text('提交后账号将进入注销排期，期间可撤销。确认提交？'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false), child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('确认注销',
                  style: TextStyle(color: BrandColors.error))),
        ],
      ),
    );
    if (sure != true || !mounted) return;
    setState(() => _submitting = true);
    try {
      if (auth.token.startsWith('mock-')) {
        await auth.logout();
        return;
      }
      await repo.requestAccountDeletion(_confirmText);
      await auth.refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已提交注销')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('提交失败，请稍后重试')));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _cancel() async {
    final auth = context.read<AuthController>();
    final repo = context.read<UserRepository>();
    setState(() => _submitting = true);
    try {
      await repo.cancelAccountDeletion();
      await auth.refresh();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已撤销注销')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('撤销失败，请稍后重试')));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheduledAt =
        context.watch<AuthController>().user?.accountDeletionScheduledAt;
    return Scaffold(
      appBar: AppBar(title: const Text('注销账号')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          Text('注销说明',
              style: TextStyle(
                  fontSize: rpx(34),
                  fontWeight: FontWeight.w700,
                  color: BrandColors.textPrimary)),
          SizedBox(height: rpx(16)),
          Container(
            padding: EdgeInsets.all(rpx(28)),
            decoration: BoxDecoration(
              color: BrandColors.amberBg,
              borderRadius: BorderRadius.circular(Radii.md),
            ),
            child: Text(
              '注销后，你的账号与数据将在保留期后被永久删除，且不可恢复，包括：分析报告、训练记录、对话历史等。'
              '已产生的订单不受影响。',
              style: TextStyle(
                  fontSize: rpx(28), height: 1.6, color: BrandColors.amber),
            ),
          ),
          SizedBox(height: rpx(40)),
          if (scheduledAt != null)
            _scheduledView(scheduledAt)
          else
            _confirmView(),
        ],
      ),
    );
  }

  Widget _scheduledView(String scheduledAt) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: EdgeInsets.all(rpx(28)),
            decoration: BoxDecoration(
              color: BrandColors.error.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(Radii.md),
              border: Border.all(color: BrandColors.error.withValues(alpha: 0.4)),
            ),
            child: Text('当前状态：已排期注销，预计时间：${scheduledAt.split('T').first}',
                style: TextStyle(
                    fontSize: rpx(28), color: BrandColors.error)),
          ),
          SizedBox(height: rpx(40)),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _submitting ? null : _cancel,
              child: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('撤销注销'),
            ),
          ),
          SizedBox(height: rpx(20)),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () async {
                await context.read<AuthController>().logout();
              },
              child: const Text('退出并返回登录'),
            ),
          ),
        ],
      );

  Widget _confirmView() => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('在下方输入框中输入大写 DELETE 以确认注销',
              style: TextStyle(
                  fontSize: rpx(30), color: BrandColors.textPrimary)),
          SizedBox(height: rpx(16)),
          TextField(
            controller: _ctl,
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(
              hintText: '输入 DELETE',
              filled: true,
              fillColor: BrandColors.bgCard,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(Radii.md),
                borderSide: const BorderSide(color: BrandColors.border),
              ),
            ),
          ),
          SizedBox(height: rpx(48)),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _submitting ? null : _submit,
              style: ElevatedButton.styleFrom(
                backgroundColor: BrandColors.error,
                padding: EdgeInsets.symmetric(vertical: rpx(24)),
              ),
              child: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('确认注销'),
            ),
          ),
          SizedBox(height: rpx(20)),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('返回'),
            ),
          ),
        ],
      );
}
