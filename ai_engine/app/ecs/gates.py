"""ECS v1 漂移门禁阈值（对齐 docs/release-notes/ecs-v1-starter-checklist.md §4）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DriftLevel = Literal["pass", "yellow", "red"]


@dataclass(frozen=True)
class EcsDriftGateConfig:
    overall_yellow: float = 5.0
    phase_yellow: float = 8.0
    teaching_overall_floor: float = 80.0
    bulk_drift_yellow: float = 3.0
    bulk_drift_ratio: float = 0.5


@dataclass(frozen=True)
class EcsDriftFinding:
    level: DriftLevel
    clip_id: str
    field: str
    message: str


def evaluate_clip_drift(
    *,
    clip_id: str,
    clip_class: str,
    baseline_overall: int,
    current_overall: int,
    baseline_phases: dict[str, int],
    current_phases: dict[str, int],
    config: EcsDriftGateConfig | None = None,
) -> list[EcsDriftFinding]:
    """单条样本与基线对比；返回 pass/yellow/red 发现项。"""
    cfg = config or EcsDriftGateConfig()
    findings: list[EcsDriftFinding] = []

    overall_delta = current_overall - baseline_overall
    if abs(overall_delta) > cfg.overall_yellow:
        findings.append(
            EcsDriftFinding(
                level="yellow",
                clip_id=clip_id,
                field="overall",
                message=f"overall delta {overall_delta:+d} 超过 ±{cfg.overall_yellow:g}",
            )
        )

    if clip_class == "teaching" and current_overall < cfg.teaching_overall_floor:
        findings.append(
            EcsDriftFinding(
                level="red",
                clip_id=clip_id,
                field="overall",
                message=(
                    f"teaching 标杆 overall={current_overall} "
                    f"< {cfg.teaching_overall_floor:g}（标红门禁）"
                ),
            )
        )

    for phase, base_score in baseline_phases.items():
        cur = current_phases.get(phase)
        if cur is None:
            findings.append(
                EcsDriftFinding(
                    level="red",
                    clip_id=clip_id,
                    field=phase,
                    message=f"缺少阶段分 {phase}",
                )
            )
            continue
        delta = cur - base_score
        if abs(delta) > cfg.phase_yellow:
            findings.append(
                EcsDriftFinding(
                    level="yellow",
                    clip_id=clip_id,
                    field=phase,
                    message=f"{phase} delta {delta:+d} 超过 ±{cfg.phase_yellow:g}",
                )
            )

    if not any(f.level == "red" for f in findings):
        findings.append(
            EcsDriftFinding(
                level="pass",
                clip_id=clip_id,
                field="summary",
                message="单条样本在阈值内",
            )
        )

    return findings


def evaluate_bulk_drift(
    *,
    clip_ids: list[str],
    overall_deltas: dict[str, int],
    config: EcsDriftGateConfig | None = None,
) -> EcsDriftFinding | None:
    """50% 以上样本同方向 overall 漂移 > ±3 → 标红。"""
    cfg = config or EcsDriftGateConfig()
    if not clip_ids:
        return None

    pos = sum(1 for cid in clip_ids if overall_deltas.get(cid, 0) > cfg.bulk_drift_yellow)
    neg = sum(1 for cid in clip_ids if overall_deltas.get(cid, 0) < -cfg.bulk_drift_yellow)
    n = len(clip_ids)
    ratio = cfg.bulk_drift_ratio

    if pos / n >= ratio:
        return EcsDriftFinding(
            level="red",
            clip_id="*",
            field="bulk",
            message=f"{pos}/{n} 样本 overall 正向漂移 > +{cfg.bulk_drift_yellow:g}（标红门禁）",
        )
    if neg / n >= ratio:
        return EcsDriftFinding(
            level="red",
            clip_id="*",
            field="bulk",
            message=f"{neg}/{n} 样本 overall 负向漂移 < -{cfg.bulk_drift_yellow:g}（标红门禁）",
        )
    return None


def worst_level(findings: list[EcsDriftFinding]) -> DriftLevel:
    if any(f.level == "red" for f in findings):
        return "red"
    if any(f.level == "yellow" for f in findings):
        return "yellow"
    return "pass"
