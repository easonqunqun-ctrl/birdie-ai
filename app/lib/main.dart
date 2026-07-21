import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/storage.dart';
import 'data/repositories/analysis_repository.dart';
import 'data/repositories/chat_repository.dart';
import 'data/repositories/content_repository.dart';
import 'data/repositories/training_repository.dart';
import 'data/repositories/user_repository.dart';
import 'features/analysis/analysis_controller.dart';
import 'features/auth/auth_controller.dart';
import 'features/coach/chat_controller.dart';
import 'nav/app_gate.dart';
import 'theme/app_theme.dart';
import 'widgets/env_badge.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppStorage.instance.init();

  late final ApiClient api;
  late final AuthController auth;
  api = ApiClient(onUnauthorized: () => auth.onUnauthorized());
  final userRepo = UserRepository(api);
  final analysisRepo = AnalysisRepository(api);
  final chatRepo = ChatRepository(api);
  final trainingRepo = TrainingRepository(api);
  final contentRepo = ContentRepository(api);
  auth = AuthController(userRepo);
  // 冷启动恢复登录态
  auth.bootstrap();

  runApp(BirdieApp(
    auth: auth,
    api: api,
    userRepo: userRepo,
    analysisRepo: analysisRepo,
    chatRepo: chatRepo,
    trainingRepo: trainingRepo,
    contentRepo: contentRepo,
  ));
}

class BirdieApp extends StatelessWidget {
  const BirdieApp({
    super.key,
    required this.auth,
    required this.api,
    required this.userRepo,
    required this.analysisRepo,
    required this.chatRepo,
    required this.trainingRepo,
    required this.contentRepo,
  });

  final AuthController auth;
  final ApiClient api;
  final UserRepository userRepo;
  final AnalysisRepository analysisRepo;
  final ChatRepository chatRepo;
  final TrainingRepository trainingRepo;
  final ContentRepository contentRepo;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthController>.value(value: auth),
        Provider<ApiClient>.value(value: api),
        Provider<UserRepository>.value(value: userRepo),
        Provider<AnalysisRepository>.value(value: analysisRepo),
        Provider<TrainingRepository>.value(value: trainingRepo),
        Provider<ContentRepository>.value(value: contentRepo),
        ChangeNotifierProvider<AnalysisController>(
          create: (_) => AnalysisController(analysisRepo),
        ),
        ChangeNotifierProvider<ChatController>(
          create: (_) => ChatController(chatRepo),
        ),
      ],
      child: MaterialApp(
        title: '领翼golf',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const AppGate(),
        builder: (context, child) => Stack(
          children: [
            ?child,
            const EnvBadge(),
          ],
        ),
      ),
    );
  }
}
