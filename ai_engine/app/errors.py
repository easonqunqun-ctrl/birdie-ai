"""AI Engine 业务异常。

设计思路
--------
- 所有 pipeline 内部**抛** `PipelineError` 子类；`main.py::analyze` **捕获**后统一
  转成 `AnalyzeResult(status="failed", error_code=..., error_message=...)` 返回给
  后端。后端 `integrations/ai_engine.py` 再把 `error_code` 原样透传成 HTTP 错误码
  映射到前端（见 `docs/02-API接口设计文档.md §1.4`）。

- **为什么不抛 HTTPException？**
  `/analyze` 的 HTTP 层**永远返回 200**，失败语义走 body 里的 `status="failed"`；
  这样 Celery 侧拿到响应就能判断成功/失败，而不用同时处理两种异常通道
  （后端侧也已经按这个约定实现，见 `backend/app/integrations/ai_engine.py`）。

错误码表（docs/02 §1.4 约定的 50101-50105 段 + docs/23 §3.2 / §11.4 P2 扩展段）
-----------------------------------------------------------------------------
| code  | 类                  | 典型触发 |
|-------|---------------------|---------|
| 50101 | `PreprocessError`   | 文件下载失败 / 容器损坏 / ffprobe 读取失败（一期行为，不变） |
| 50102 | `PoorQualityError`  | 清晰度不足（拉普拉斯方差 < 阈值）或稳像失败 |
| 50103 | `NoPersonError`     | MediaPipe 全帧无人体 / 有效帧占比 < 70% |
| 50104 | `NoSwingError`      | 检测到人但无挥杆动作（W6-T2 阶段分割里用） |
| 50105 | `PoseModelError`    | MediaPipe 模型初始化失败 / 推理异常 |
| 50120 | `DecodeError`       | **P2-M7-02**：codec/容器不被本镜像支持（HEVC/HDR/VP9 转码失败） |

P2-M7-02 拆分原则
-----------------
- 50101 仍负责"网络/容器层"硬伤：curl 失败、文件损坏、ffprobe 无法读
- 50120 专管"codec 层"语义：ffmpeg 能找到流但无法解 / tonemap / 转 yuv420p
- 客户端 50120 文案统一为「视频格式暂不支持」（详见 P2-M7-03）
- backend `analysis_tasks` 退配额段需含 50120（见 docs/23 §11.4）
"""

from __future__ import annotations


class PipelineError(Exception):
    """所有 pipeline 级异常的基类。

    子类**必须**提供 `code`（业务错误码，int）和 `user_message`（面向终端
    用户的中文文案）。`args[0]` 作为技术细节（用于日志）。
    """

    code: int = 50100  # 通用兜底；实际使用时由子类覆盖
    user_message: str = "分析失败，请稍后重试"

    def __init__(self, detail: str = "", *, user_message: str | None = None) -> None:
        super().__init__(detail or self.user_message)
        if user_message is not None:
            self.user_message = user_message
        self.detail = detail

    def to_dict(self) -> dict[str, str | int]:
        return {
            "code": self.code,
            "message": self.user_message,
            "detail": self.detail,
        }


class PreprocessError(PipelineError):
    """视频预处理失败：ffmpeg 转码报错、文件损坏、下载失败等。"""

    code = 50101
    user_message = "视频处理失败，请重新上传"


class PoorQualityError(PipelineError):
    """视频画质不足：清晰度过低 / 抖动过大 / 分辨率过小。

    阈值在 `preprocess.py::QUALITY_THRESHOLDS` 里集中管理；对应到 MVP §4.1
    的"视频质量"校验（客户端会先做一遍，服务端再兜一次）。
    """

    code = 50102
    user_message = "视频画质不足，建议在光线充足的环境下重拍"


class NoPersonError(PipelineError):
    """MediaPipe 全帧未检测到人体，或有效帧占比过低。

    典型场景：纯黑视频 / 风景视频 / 镜头没对准球员。
    """

    code = 50103
    user_message = "视频中未检测到挥杆动作，请确保人物完整入镜"


class NoSwingError(PipelineError):
    """检测到人体但无挥杆动作（静止、走路、其它运动）。

    由 W6-T2 阶段分割环节抛出：关键点序列不满足挥杆的"上杆-顶点-下杆"
    速度曲线特征。T1 这里先占位，保证错误码映射完整。
    """

    code = 50104
    user_message = "未检测到完整的挥杆动作，请重新拍摄"


class PoseModelError(PipelineError):
    """MediaPipe 初始化 / 推理过程中抛异常（非预期的内部错误）。

    一般表明环境问题（GLIBC / 模型文件损坏），需要运维介入。
    """

    code = 50105
    user_message = "AI 引擎内部异常，请稍后再试"


class DecodeError(PipelineError):
    """P2-M7-02：codec/容器不被本镜像支持，无法解码或转码到 yuv420p。

    典型触发：
    - HEVC / H.265 但镜像未编入 libx265（旧基线镜像）
    - 10-bit HDR + bt2020 但镜像缺 libzimg（zscale tonemap 链失败）
    - VP9 .webm 但镜像未编入 libvpx
    - container_format_name 在白名单外（如 .mkv / .3gp）

    与 50101 的区别：50101 是"完全没拿到视频/容器损坏"；50120 是"拿到了但解不了"。
    backend 退配额段已扩到含 50120（docs/23 §11.4），客户端文案见 docs/23 §11.5 +
    P2-M7-03 kickoff（统一为「视频格式暂不支持」）。
    """

    code = 50120
    user_message = "视频格式暂不支持，请使用 H.264 / mp4 格式重新拍摄"
