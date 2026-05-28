"""External integrations 模块根（P2-W14-D）.

把"调外部资源（MinIO / 对象存储 / ffprobe / 第三方 API）"的胶水代码从 pipeline
主体里抽出来，便于：
- 单点测试（不依赖完整 pipeline 跑）
- W18+ 切 COS / 第三方对象存储时只动一个模块
- W16+ 加 backend `_probe_video_url` 等共享集成时直接 import 复用
"""
