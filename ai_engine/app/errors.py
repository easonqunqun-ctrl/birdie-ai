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

错误码表（docs/02 §1.4 约定的 50101-50105 段 + P2-M7-02/03 扩展 50106-50123）
-----------------------------------------------------------------------------
| code  | 类                          | 典型触发 |
|-------|-----------------------------|---------|
| 50101 | `PreprocessError`           | 下载/容器损坏（M7-02 起：codec 走 50120） |
| 50102 | `PoorQualityError`          | 综合画质兜底（M7-03 起：暗光/抖动/清晰度有细分码） |
| 50103 | `NoPersonError`             | MediaPipe 全帧无人体 |
| 50104 | `NoSwingError`              | 检测到人但无挥杆动作 |
| 50105 | `PoseModelError`            | MediaPipe 初始化/推理失败 |
| 50106 | `VideoTooShortError`        | duration < MIN |
| 50107 | `VideoTooLongError`         | duration > MAX |
| 50108 | `ResolutionTooLowError`     | 短边 < 720（V2） |
| 50109 | `LowLightError`             | clarity_score < MIN |
| 50110 | `CameraShakeError`          | stability < HARD_BLOCK |
| 50111 | `UnstableClarityError`      | low_clarity_frame_ratio > 阈值 |
| 50112 | `CompositeQualityError`     | 综合 quality_score < MIN |
| 50113 | `PartialBodyError`          | 半身入镜（AC-3 四场景） |
| 50114 | `LowPoseConfidenceError`    | warn：pose 有效帧占比偏低 |
| 50115 | `FrameDecodeLossError`      | frame_loss > 阈值 |
| 50116 | `KeypointMissingError`      | 关键帧 visibility 持续缺失 |
| 50117 | `OrientationUnsupportedError` | 旋转元数据异常 |
| 50118 | `AnalysisTimeoutError`      | pipeline SLA 超时 |
| 50119 | `EngineOverloadError`       | 队列积压 |
| 50120 | `DecodeError`               | **P2-M7-02**：codec/HDR/HEVC/VP9 转码失败（详 DecodeError docstring） |
| 50121 | `SlowmoMetadataError`       | 慢动作元数据无法解析（M7-02） |
| 50122 | `MultiSwingOverflowError`   | >5 段挥杆候选（M7-07，占位） |
| 50123 | `ModeClubMismatchError`     | mode 与 club_type 不匹配（M10，占位） |

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


# ============================================================
# P2-M7-03：细分错误码 50106-50123（详 docs/release-notes/p2-m7-03-error-codes-kickoff.md §3.1）
#
# 设计要点：
# - 一期 50101-50105 全部保留（向后兼容；50101 收窄为下载/容器损坏；50102 作画质兜底）
# - precheck 早失败映射详见 §5.1：preprocess 内 enforce_quality_gates 按 stats 抛细分码
# - 50120/50121 与 M7-02 联调（codec / 慢动作元数据）
# - 50122/50123 占位注册：业务触发归 M7-07 / M10 PR，本任务仅注册类 + 文案
# ============================================================


class VideoTooShortError(PipelineError):
    """50106：duration < MIN_DURATION_SEC（precheck 早失败）。"""

    code = 50106
    user_message = "挥杆视频至少拍 2 秒，请包含完整上杆到收杆后再上传"


class VideoTooLongError(PipelineError):
    """50107：duration > MAX_DURATION_SEC。"""

    code = 50107
    user_message = "单段挥杆请控制在 30 秒以内，只拍一次挥杆动作即可"


class ResolutionTooLowError(PipelineError):
    """50108：短边低于 V2 分层阈值（720）。"""

    code = 50108
    user_message = "请在手机设置中选 1080p 及以上，并确保球员清晰占画面 1/2 以上"


class LowLightError(PipelineError):
    """50109：clarity_score < MIN_CLARITY → 光线不足。"""

    code = 50109
    user_message = "请在光线充足的练习场或户外重拍，避免逆光与强阴影"


class CameraShakeError(PipelineError):
    """50110：stability_score < MIN_STABILITY_HARD_BLOCK → 画面抖动过大。"""

    code = 50110
    user_message = "请固定手机或使用三脚架，拍摄时避免手持晃动"


class UnstableClarityError(PipelineError):
    """50111：low_clarity_frame_ratio > 阈值 → 清晰度不稳定。"""

    code = 50111
    user_message = "拍摄时保持对焦清晰，避免半清晰半模糊；擦净镜头后重拍"


class CompositeQualityError(PipelineError):
    """50112：综合 quality_score 不达标（未归类到 50109-50111 的画质失败）。

    保留作 50102 升级版兜底；Sentry 上记 `unmapped_quality_gate` 供 W19 迭代消减。
    """

    code = 50112
    user_message = "请改善光线、稳定机位并确保全身入镜后重新拍摄"


class PartialBodyError(PipelineError):
    """50113：关键点可见性不足 / 半身入镜（AC-3 真机回归四场景之一）。"""

    code = 50113
    user_message = "请退后 2-3 米，确保头到脚完整出现在画面中再拍"


class LowPoseConfidenceError(PipelineError):
    """50114：pose 有效帧占比偏低但未达 NoPerson（warn 级，业务可决策放行 vs 重拍）。"""

    code = 50114
    user_message = "请穿与背景对比明显的服装，避免遮挡，在简洁背景下重拍"


class FrameDecodeLossError(PipelineError):
    """50115：frame_loss_ratio > 阈值 → 解码丢帧严重。"""

    code = 50115
    user_message = "请重新导出或另存视频后再上传；避免使用损坏的文件"


class KeypointMissingError(PipelineError):
    """50116：关键帧肩/髋/腕 visibility 持续缺失。"""

    code = 50116
    user_message = "请确保侧向或正对机位，球员不要被球包/他人遮挡"


class OrientationUnsupportedError(PipelineError):
    """50117：极端竖屏 / 旋转元数据异常。"""

    code = 50117
    user_message = "请在系统相机中关闭异常旋转，竖屏正常握持拍摄"


class AnalysisTimeoutError(PipelineError):
    """50118：pipeline 总耗时超 SLA。"""

    code = 50118
    user_message = "请缩短视频时长或稍后重试；持续出现请联系客服"


class EngineOverloadError(PipelineError):
    """50119：队列积压 / 并发超限（运维侧触发）。"""

    code = 50119
    user_message = "当前分析人数较多，请稍后再试"


class DecodeError(PipelineError):
    """50120：codec/HDR/HEVC/VP9 转码失败（M7-02 抛；客户端文案归 M7-03）。

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


class SlowmoMetadataError(PipelineError):
    """50121：mov 慢动作元数据无法解析（M7-02 抛；客户端文案归本任务）。"""

    code = 50121
    user_message = "请用普通模式拍摄，或在相册中「转换为兼容格式」后再上传"


class MultiSwingOverflowError(PipelineError):
    """50122：检测到 >5 段挥杆候选（M7-07 触发，本任务仅占位注册）。"""

    code = 50122
    user_message = "请每段视频只拍一次挥杆，或剪辑掉多余动作后再上传"


class ModeClubMismatchError(PipelineError):
    """50123：mode 与 club_type 不匹配（M10 触发，本任务仅占位注册）。"""

    code = 50123
    user_message = "推杆分析请选择推杆模式；全挥杆请勿选推杆"


# ============================================================
# P2-M7-03 错误码 registry
# FR-2 enum 注册中心；单测 (test_error_registry.py) 据此断言全表覆盖
# CI 门禁：客户端 analysisEngineErrors.ts 必须覆盖 ERROR_REGISTRY 全键
# ============================================================

ERROR_REGISTRY: dict[int, type[PipelineError]] = {
    # 一期保留段（50101-50105）
    50101: PreprocessError,
    50102: PoorQualityError,
    50103: NoPersonError,
    50104: NoSwingError,
    50105: PoseModelError,
    # P2-M7-03 扩展段（50106-50123）
    50106: VideoTooShortError,
    50107: VideoTooLongError,
    50108: ResolutionTooLowError,
    50109: LowLightError,
    50110: CameraShakeError,
    50111: UnstableClarityError,
    50112: CompositeQualityError,
    50113: PartialBodyError,
    50114: LowPoseConfidenceError,
    50115: FrameDecodeLossError,
    50116: KeypointMissingError,
    50117: OrientationUnsupportedError,
    50118: AnalysisTimeoutError,
    50119: EngineOverloadError,
    50120: DecodeError,
    50121: SlowmoMetadataError,
    50122: MultiSwingOverflowError,
    50123: ModeClubMismatchError,
}


def get_error_class(code: int) -> type[PipelineError]:
    """按 code 查异常类；未注册返回 PipelineError 兜底。"""
    return ERROR_REGISTRY.get(code, PipelineError)


def all_registered_codes() -> list[int]:
    """供单测 / CI 客户端文案校验使用。"""
    return sorted(ERROR_REGISTRY.keys())
