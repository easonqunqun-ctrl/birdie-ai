import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/auth/auth_controller.dart';
import '../features/auth/pages/login_page.dart';

/// 未登录则 push 登录页；已登录返回 true。
Future<bool> requireLogin(BuildContext context) async {
  final auth = context.read<AuthController>();
  if (auth.isLoggedIn) return true;
  await Navigator.of(context).push<void>(
    MaterialPageRoute(builder: (_) => const LoginPage()),
  );
  if (!context.mounted) return false;
  return context.read<AuthController>().isLoggedIn;
}
