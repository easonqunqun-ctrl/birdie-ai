"""ECS v1 回归快照：对 manifest 中每条样本跑 scoring 子链路并对比基线。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.ecs.gates import (
    EcsDriftFinding,
    EcsDriftGateConfig,
    evaluate_bulk_drift,
    evaluate_clip_drift,
    worst_level,
)
from app.pipeline.constants import PHASE_ORDER
from app.pipeline.features import extract_features
from app.pipeline.phases import segment_phases
from app.pipeline.pose import PoseResult
from app.pipeline.scoring import score_all_phases, score_overall


class PoseProfileBuilder(Protocol):
    def __call__(self, profile: str) -> PoseResult: ...


@dataclass(frozen=True)
class EcsClipManifest:
    ecs_clip_id: str
    class_: str
    pose_profile: str
    notes: str = ""


@dataclass(frozen=True)
class EcsManifest:
    version: str
    description: str
    clips: tuple[EcsClipManifest, ...]


@dataclass(frozen=True)
class EcsClipScores:
    overall: int
    phase_scores: dict[str, int]


@dataclass(frozen=True)
class EcsRegressionReport:
    manifest_version: str
    level: str
    clip_findings: dict[str, list[EcsDriftFinding]]
    bulk_finding: EcsDriftFinding | None
    current: dict[str, EcsClipScores]
    baseline: dict[str, EcsClipScores]


def default_ecs_v1_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "ecs" / "v1"


def load_manifest(path: Path) -> EcsManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    clips = tuple(
        EcsClipManifest(
            ecs_clip_id=str(c["ecs_clip_id"]),
            class_=str(c["class"]),
            pose_profile=str(c["pose_profile"]),
            notes=str(c.get("notes", "")),
        )
        for c in raw["clips"]
    )
    return EcsManifest(
        version=str(raw["version"]),
        description=str(raw.get("description", "")),
        clips=clips,
    )


def load_baseline_snapshot(path: Path) -> dict[str, EcsClipScores]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, EcsClipScores] = {}
    for clip_id, payload in raw["clips"].items():
        phases = {str(k): int(v) for k, v in payload["phase_scores"].items()}
        out[clip_id] = EcsClipScores(overall=int(payload["overall"]), phase_scores=phases)
    return out


def score_pose_profile(pose: PoseResult) -> EcsClipScores:
    phases = segment_phases(pose)
    features = extract_features(pose.keypoints, phases)
    phase_scores = score_all_phases(features)
    overall = score_overall(phase_scores)
    return EcsClipScores(
        overall=int(overall),
        phase_scores={p: int(phase_scores[p]) for p in PHASE_ORDER},
    )


def generate_snapshot(
    manifest: EcsManifest,
    build_pose: PoseProfileBuilder,
) -> dict[str, Any]:
    clips: dict[str, Any] = {}
    for clip in manifest.clips:
        scores = score_pose_profile(build_pose(clip.pose_profile))
        clips[clip.ecs_clip_id] = {
            "overall": scores.overall,
            "phase_scores": scores.phase_scores,
            "class": clip.class_,
            "pose_profile": clip.pose_profile,
        }
    return {
        "version": manifest.version,
        "clips": clips,
    }


def run_regression(
    *,
    manifest: EcsManifest,
    baseline: dict[str, EcsClipScores],
    build_pose: PoseProfileBuilder,
    config: EcsDriftGateConfig | None = None,
) -> EcsRegressionReport:
    cfg = config or EcsDriftGateConfig()
    current: dict[str, EcsClipScores] = {}
    clip_findings: dict[str, list[EcsDriftFinding]] = {}
    overall_deltas: dict[str, int] = {}

    for clip in manifest.clips:
        cur = score_pose_profile(build_pose(clip.pose_profile))
        current[clip.ecs_clip_id] = cur
        base = baseline.get(clip.ecs_clip_id)
        if base is None:
            clip_findings[clip.ecs_clip_id] = [
                EcsDriftFinding(
                    level="red",
                    clip_id=clip.ecs_clip_id,
                    field="baseline",
                    message="基线快照缺少该样本",
                )
            ]
            continue

        overall_deltas[clip.ecs_clip_id] = cur.overall - base.overall
        clip_findings[clip.ecs_clip_id] = evaluate_clip_drift(
            clip_id=clip.ecs_clip_id,
            clip_class=clip.class_,
            baseline_overall=base.overall,
            current_overall=cur.overall,
            baseline_phases=base.phase_scores,
            current_phases=cur.phase_scores,
            config=cfg,
        )

    bulk = evaluate_bulk_drift(
        clip_ids=[c.ecs_clip_id for c in manifest.clips],
        overall_deltas=overall_deltas,
        config=cfg,
    )

    all_findings: list[EcsDriftFinding] = [f for fs in clip_findings.values() for f in fs]
    if bulk:
        all_findings.append(bulk)

    return EcsRegressionReport(
        manifest_version=manifest.version,
        level=worst_level(all_findings),
        clip_findings=clip_findings,
        bulk_finding=bulk,
        current=current,
        baseline=baseline,
    )


def assert_regression_pass(report: EcsRegressionReport) -> None:
    if report.level == "red":
        msgs = []
        for fs in report.clip_findings.values():
            for f in fs:
                if f.level == "red":
                    msgs.append(f"{f.clip_id}/{f.field}: {f.message}")
        if report.bulk_finding and report.bulk_finding.level == "red":
            msgs.append(report.bulk_finding.message)
        raise AssertionError("ECS 回归标红：\n" + "\n".join(msgs))
