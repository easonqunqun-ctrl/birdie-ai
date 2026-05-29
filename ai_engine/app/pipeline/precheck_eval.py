"""P-02 · precheck 阈值离线评估（纯逻辑）。

为什么需要这个
--------------
``run_precheck``（``app/pipeline/precheck.py``）对上传视频做硬门槛拦截
（``too_dark`` / ``too_blurry`` / ``too_shaky`` / 时长越界）。真实用户上传非高尔夫或
低质视频累计 ≥5 例后（见 ``docs/release-notes/wait-for-triggers-checklist.md`` §2.3），
需要把「AI 拦没拦」对照「人工标注该不该拦」算混淆矩阵，看 **误杀**（拦了正常视频，
伤体验）与 **漏拦**（放过了该拦的，浪费一次分析配额）各有多少，再决定调哪个阈值。

纯函数设计
----------
本模块只处理「一条样本的人工标签 + AI 判定」到混淆矩阵的聚合，**不下载视频、不调
ffprobe**。把跑 ``run_precheck`` 的 I/O 留给 ``scripts/precheck_threshold_eval.py``，
因此评估逻辑可被单测完全确定性覆盖。

约定
----
- 人工标签 ``label``：``"block"``（该拦）/ ``"pass"``（该放行）。把「该拦」视作正类。
- AI 判定 ``decision``：``"blocked"`` / ``"passed"``（即 ``PrecheckResult.status``）。
- 混淆：
  - TP：该拦且拦了；TN：该放且放了；
  - **FP（误杀）**：该放却拦了 —— 最伤体验，调阈值首要压低；
  - **FN（漏拦）**：该拦却放了 —— 浪费配额 / 出垃圾报告。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

Label = Literal["block", "pass"]
Decision = Literal["blocked", "passed"]


@dataclass(frozen=True)
class PrecheckEvalSample:
    """一条已判定 + 已标注的评估样本。"""

    video_url: str
    label: Label
    decision: Decision
    error_code: int | None = None
    note: str = ""

    @property
    def is_true_positive(self) -> bool:
        return self.label == "block" and self.decision == "blocked"

    @property
    def is_false_positive(self) -> bool:
        """误杀：人工判正常，AI 却拦了。"""
        return self.label == "pass" and self.decision == "blocked"

    @property
    def is_false_negative(self) -> bool:
        """漏拦：人工判该拦，AI 却放了。"""
        return self.label == "block" and self.decision == "passed"

    @property
    def is_true_negative(self) -> bool:
        return self.label == "pass" and self.decision == "passed"


@dataclass(frozen=True)
class PrecheckEvalReport:
    total: int
    tp: int
    fp: int
    fn: int
    tn: int
    false_positives: list[PrecheckEvalSample] = field(default_factory=list)
    false_negatives: list[PrecheckEvalSample] = field(default_factory=list)
    # 误杀样本的 error_code 分布（哪个硬门槛在误杀），用于定位调哪个阈值
    false_positive_codes: dict[int, int] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        """拦截精确率：AI 拦的里面真正该拦的占比。低 → 误杀多。"""
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        """拦截召回率：该拦的里面 AI 真拦住的占比。低 → 漏拦多。"""
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def false_positive_rate(self) -> float:
        """误杀率：正常视频里被错拦的占比。"""
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0


def evaluate(samples: list[PrecheckEvalSample]) -> PrecheckEvalReport:
    """聚合一组样本为混淆矩阵报告。"""
    tp = [s for s in samples if s.is_true_positive]
    fp = [s for s in samples if s.is_false_positive]
    fn = [s for s in samples if s.is_false_negative]
    tn = [s for s in samples if s.is_true_negative]

    fp_codes: Counter[int] = Counter(
        s.error_code for s in fp if s.error_code is not None
    )

    return PrecheckEvalReport(
        total=len(samples),
        tp=len(tp),
        fp=len(fp),
        fn=len(fn),
        tn=len(tn),
        false_positives=fp,
        false_negatives=fn,
        false_positive_codes=dict(fp_codes.most_common()),
    )


def tuning_hint(report: PrecheckEvalReport) -> str:
    """给出一句话调参方向。"""
    if report.total == 0:
        return "无样本，无法评估。"
    if report.fp == 0 and report.fn == 0:
        return "✅ 误杀 / 漏拦均为 0，当前阈值与本批标注完全一致，无需调整。"
    hints: list[str] = []
    if report.fp > 0:
        top = ", ".join(
            f"code={code}×{n}" for code, n in report.false_positive_codes.items()
        )
        hints.append(
            f"⚠️ 误杀 {report.fp} 例（精确率 {report.precision:.2f}）"
            f"——放宽对应硬门槛阈值；误杀错误码分布：{top or '未知'}"
        )
    if report.fn > 0:
        hints.append(
            f"⚠️ 漏拦 {report.fn} 例（召回率 {report.recall:.2f}）"
            "——收紧对应硬门槛阈值，或补检测维度"
        )
    return " ".join(hints)
