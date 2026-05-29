"""ENG-04 标定集 · issue 检测 F1 评估 + 回归门禁（离线纯逻辑）。

与 ``app/ecs/regression.py`` 正交
--------------------------------
- ``regression.py``：看 ``overall`` / 阶段分**漂移**（连续值偏移门禁）；
- 本模块：看 **issue 检测**的准确率 / 召回率 / F1，对照**人工标注 ground truth**。

为什么需要这个
--------------
``docs/20`` ECS 标定集积累到争议样本 ≥20（见
``docs/release-notes/wait-for-triggers-checklist.md`` §2.7）后，调 YAML / 规则阈值
有引入回归的风险——某个 issue 类型可能因为阈值收紧而漏检（recall 掉），或放宽而误检
（precision 掉）。本模块把「每个 issue 类型的 F1 不得相对 baseline 跌超过阈值」做成
**可门禁的定量凭证**，供 ``scripts/calibration_regression.py`` 在改阈值前后对比。

纯函数设计
----------
本模块**不触碰** pose / 视频 / 网络，只接收「预测 issue 集合」与「ground-truth issue
集合」两个 ``dict[clip_id, set[issue_type]]``，因此可被单测完全确定性地覆盖。把「跑
pipeline 拿预测」的 I/O 留给 CLI 脚本。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 默认 F1 回归门禁：任一类型 F1 相对 baseline 跌超过该值即标红 block PR。
# 对齐 wait-for-triggers-checklist §2.7「F1 score 跌幅 > 5% → block PR」。
DEFAULT_MAX_F1_DROP = 0.05


@dataclass(frozen=True)
class IssueDetectionStats:
    """单个 issue 类型在整组标定样本上的检测统计。"""

    issue_type: str
    tp: int
    fp: int
    fn: int

    @property
    def support(self) -> int:
        """ground-truth 正样本数（该类型在多少条样本里**应当**被检出）。"""
        return self.tp + self.fn

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def compute_detection_stats(
    predicted: dict[str, set[str]],
    ground_truth: dict[str, set[str]],
) -> dict[str, IssueDetectionStats]:
    """对照预测与标注，逐 issue 类型聚合 TP / FP / FN。

    Args:
        predicted: ``{clip_id: {issue_type, ...}}`` —— pipeline 实际检出的 issue。
        ground_truth: ``{clip_id: {issue_type, ...}}`` —— 人工标注**应当**检出的 issue。

    Returns:
        ``{issue_type: IssueDetectionStats}``，覆盖出现在任一侧的所有类型，按类型名排序。
    """
    types: set[str] = set()
    for s in predicted.values():
        types |= s
    for s in ground_truth.values():
        types |= s

    clip_ids = set(predicted) | set(ground_truth)
    out: dict[str, IssueDetectionStats] = {}
    for t in sorted(types):
        tp = fp = fn = 0
        for cid in clip_ids:
            pred = t in predicted.get(cid, set())
            gt = t in ground_truth.get(cid, set())
            if pred and gt:
                tp += 1
            elif pred and not gt:
                fp += 1
            elif gt and not pred:
                fn += 1
        out[t] = IssueDetectionStats(issue_type=t, tp=tp, fp=fp, fn=fn)
    return out


def macro_f1(stats: dict[str, IssueDetectionStats]) -> float:
    """对**有 ground-truth support** 的类型取 F1 平均。

    只统计 ``support > 0`` 的类型：纯 FP（标注里从没出现过、模型乱报）的类型不该被算进
    宏平均的分母，否则一条噪声误报会把整体 F1 拉低到失真。
    """
    supported = [s for s in stats.values() if s.support > 0]
    if not supported:
        return 0.0
    return round(sum(s.f1 for s in supported) / len(supported), 4)


def per_type_f1(stats: dict[str, IssueDetectionStats]) -> dict[str, float]:
    """导出 ``{issue_type: f1}``（仅 support>0），用于落 baseline 快照。"""
    return {t: round(s.f1, 4) for t, s in stats.items() if s.support > 0}


@dataclass(frozen=True)
class F1RegressionFinding:
    level: Literal["pass", "red"]
    issue_type: str
    baseline_f1: float
    current_f1: float
    message: str


def evaluate_f1_regression(
    current: dict[str, IssueDetectionStats],
    baseline_f1: dict[str, float],
    *,
    max_f1_drop: float = DEFAULT_MAX_F1_DROP,
) -> list[F1RegressionFinding]:
    """逐 baseline 类型对比 F1；跌幅超过 ``max_f1_drop`` 即标红。

    以 **baseline 的类型集合**为准遍历：baseline 里有的类型若当前完全消失（current 无
    该类型）按 F1=0 计，必然标红——这正是「调阈值把某类型整个干掉了」的回归信号。
    """
    findings: list[F1RegressionFinding] = []
    for t in sorted(baseline_f1):
        base_f1 = baseline_f1[t]
        cur = current.get(t)
        cur_f1 = cur.f1 if cur is not None else 0.0
        drop = base_f1 - cur_f1
        if drop > max_f1_drop:
            findings.append(
                F1RegressionFinding(
                    level="red",
                    issue_type=t,
                    baseline_f1=round(base_f1, 4),
                    current_f1=round(cur_f1, 4),
                    message=(
                        f"{t} F1 {base_f1:.3f} → {cur_f1:.3f} "
                        f"（跌 {drop:.3f} > 门禁 {max_f1_drop:.3f}）"
                    ),
                )
            )
    return findings


def regression_level(findings: list[F1RegressionFinding]) -> Literal["pass", "red"]:
    return "red" if any(f.level == "red" for f in findings) else "pass"
