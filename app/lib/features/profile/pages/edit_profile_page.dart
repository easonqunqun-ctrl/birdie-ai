import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/golf_options.dart';
import '../../../theme/brand_colors.dart';
import '../../../theme/dimens.dart';
import '../../../widgets/primary_button.dart';
import '../../auth/auth_controller.dart';

/// 编辑档案：昵称 + 水平 + 目标（≤3）+ 频率。对照 profile 编辑档案子页。
class EditProfilePage extends StatefulWidget {
  const EditProfilePage({super.key});

  @override
  State<EditProfilePage> createState() => _EditProfilePageState();
}

class _EditProfilePageState extends State<EditProfilePage> {
  late TextEditingController _nickname;
  String? _level;
  late List<String> _goals;
  String? _freq;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final u = context.read<AuthController>().user;
    _nickname = TextEditingController(text: u?.nickname ?? '');
    _level = u?.golfLevel;
    _goals = List.of(u?.primaryGoals ?? const []);
    _freq = u?.weeklyPracticeFrequency;
  }

  @override
  void dispose() {
    _nickname.dispose();
    super.dispose();
  }

  void _toggleGoal(String g) {
    setState(() {
      if (_goals.contains(g)) {
        _goals.remove(g);
      } else if (_goals.length < maxGoals) {
        _goals.add(g);
      }
    });
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await context.read<AuthController>().updateProfile({
        'nickname': _nickname.text.trim(),
        if (_level != null) 'golf_level': _level,
        'primary_goals': _goals,
        if (_freq != null) 'weekly_practice_frequency': _freq,
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已保存')));
      Navigator.of(context).pop();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('保存失败，请稍后重试')));
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('编辑档案')),
      body: ListView(
        padding: EdgeInsets.all(rpx(32)),
        children: [
          _label('昵称'),
          SizedBox(height: rpx(12)),
          TextField(
            controller: _nickname,
            maxLength: 20,
            decoration: InputDecoration(
              counterText: '',
              hintText: '请输入昵称',
              filled: true,
              fillColor: BrandColors.bgCard,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(Radii.md),
                borderSide: const BorderSide(color: BrandColors.border),
              ),
            ),
          ),
          SizedBox(height: rpx(32)),
          _label('高尔夫水平'),
          SizedBox(height: rpx(16)),
          _wrap([
            for (final l in levels)
              _chip(l.label, _level == l.value,
                  () => setState(() => _level = l.value)),
          ]),
          SizedBox(height: rpx(32)),
          _label('主要目标（最多 $maxGoals 个）'),
          SizedBox(height: rpx(16)),
          _wrap([
            for (final g in goals)
              _chip(g.label, _goals.contains(g.value), () => _toggleGoal(g.value)),
          ]),
          SizedBox(height: rpx(32)),
          _label('练习频率'),
          SizedBox(height: rpx(16)),
          _wrap([
            for (final f in freqs)
              _chip(f.label, _freq == f.value,
                  () => setState(() => _freq = f.value)),
          ]),
          SizedBox(height: rpx(48)),
          PrimaryButton(label: '保存', loading: _saving, onTap: _save),
        ],
      ),
    );
  }

  Widget _label(String t) => Text(t,
      style: TextStyle(
          fontSize: rpx(30),
          fontWeight: FontWeight.w600,
          color: BrandColors.textPrimary));

  Widget _wrap(List<Widget> children) =>
      Wrap(spacing: rpx(16), runSpacing: rpx(16), children: children);

  Widget _chip(String label, bool active, VoidCallback onTap) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: rpx(28), vertical: rpx(16)),
          decoration: BoxDecoration(
            color: active ? BrandColors.primary : BrandColors.bgCard,
            borderRadius: BorderRadius.circular(rpx(32)),
            border: Border.all(
                color: active ? BrandColors.primary : BrandColors.border),
          ),
          child: Text(label,
              style: TextStyle(
                  fontSize: rpx(28),
                  color:
                      active ? BrandColors.onPrimary : BrandColors.textPrimary)),
        ),
      );
}
