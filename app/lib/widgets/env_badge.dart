import 'package:flutter/material.dart';
import '../core/env.dart';

/// 非 prod 环境角标（等价小程序 EnvBadge）。挂在根 Overlay 右上角。
class EnvBadge extends StatelessWidget {
  const EnvBadge({super.key});

  @override
  Widget build(BuildContext context) {
    if (!Env.showEnvBadge) return const SizedBox.shrink();
    final top = MediaQuery.of(context).padding.top + 48;
    return Positioned(
      top: top,
      right: 8,
      child: IgnorePointer(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            Env.envLabel,
            style: const TextStyle(color: Colors.white, fontSize: 10),
          ),
        ),
      ),
    );
  }
}
