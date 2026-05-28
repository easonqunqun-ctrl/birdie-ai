"""P2-M7-10 · 诊断规则 V2 RuleEngine 骨架。

详 docs/release-notes/p2-m7-10-rule-engine-v2-kickoff.md v0.1。

本 PR 范围（W28 起跑前置 + P2-W4 收口）
---------------------------------------
- ✅ RuleEngine 框架 + Rule / Condition 数据结构
- ✅ YAML rule loader（含 schema 校验 + 互斥矩阵）        ← P2-W4 落地
- ✅ severity 动态计算 + confidence 注入
- ✅ i18n 占位渲染（key + payload，**不**包文案）
- ✅ engine_version_tag 注入
- ✅ `rules/v2_starter.yaml`：5 条 V1→V2 入门集（W29 持续追加） ← P2-W4 落地
- ✅ `locales/zh_CN.json`：起跑期文案，与 starter 规则一一对应 ← P2-W4 落地
- ❌ 全量 15 V1 规则迁移 / 新增 10-15 规则 / 教研文案（W29-W33 PR）
- ❌ ECS 触发率验证（W34 AC-1 PR）

为什么"前置"
-------------
P2-M7-10 总工程量 ~6 PW，规则 YAML 编写 + 教研文案双签耗时较长。先把
RuleEngine + Schema + 互斥矩阵 + i18n 渲染就位，W29-W33 只需追加 yaml
文件 + locale 字典，无需动 pipeline。
"""

from __future__ import annotations

import json
import operator as op
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

ConditionOperator = Literal["<", "<=", ">", ">=", "==", "!="]
RuleEngineVersion = Literal["v2.0", "v2.1"]

# ============================================================
# 数据结构
# ============================================================


_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "<": op.lt,
    "<=": op.le,
    ">": op.gt,
    ">=": op.ge,
    "==": op.eq,
    "!=": op.ne,
}


@dataclass(frozen=True)
class RuleCondition:
    """单条规则条件。

    feature: 特征键（与 constants.FEATURES.name 对齐；不存在 → 条件为 False）
    operator: 比较运算符（< <= > >= == !=）
    threshold: 阈值（与特征同单位）
    """

    feature: str
    operator: ConditionOperator
    threshold: float

    def evaluate(self, features: Mapping[str, float]) -> bool:
        if self.feature not in features:
            return False
        fn = _OPERATORS.get(self.operator)
        if fn is None:
            return False
        try:
            return bool(fn(features[self.feature], self.threshold))
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True)
class Rule:
    """单条诊断规则。

    name: issue_type；与 constants.ISSUE_TYPES / i18n key 对齐
    display_name_key: i18n key（如 `issues.early_extension.title`）
    severity_feature: 用于动态严重度计算的特征（默认取 conditions[0].feature）
    conditions: 触发条件列表（全部 AND）
    mutually_exclusive_with: 互斥的 issue_type 列表（kickoff §3.2 mutual_exclusion.yaml）
    confidence_floor: 当 issue confidence 低于此值时不触发（默认 0.0）
    engine_version_tag: rule_engine_version（默认 v2.0）
    """

    name: str
    display_name_key: str
    conditions: tuple[RuleCondition, ...]
    severity_feature: str | None = None
    mutually_exclusive_with: tuple[str, ...] = ()
    confidence_floor: float = 0.0
    engine_version_tag: RuleEngineVersion = "v2.0"

    def evaluate(self, features: Mapping[str, float]) -> bool:
        """所有 conditions AND；空 conditions → False（防误触）。"""
        if not self.conditions:
            return False
        return all(cond.evaluate(features) for cond in self.conditions)

    def get_severity_feature(self) -> str | None:
        """优先 explicit `severity_feature`；否则 conditions[0].feature。"""
        if self.severity_feature:
            return self.severity_feature
        if self.conditions:
            return self.conditions[0].feature
        return None


@dataclass(frozen=True)
class RuleResult:
    """单条规则的诊断输出。"""

    type: str  # issue_type
    severity: float  # 0-1 动态严重度
    confidence: float  # 来自 M7-06 issue_confidence
    rule_engine_version: RuleEngineVersion
    display_name_key: str
    payload: dict[str, float] = field(default_factory=dict)


# ============================================================
# severity 动态计算（kickoff §3.3）
# ============================================================


def compute_severity(rule: Rule, features: Mapping[str, float]) -> float:
    """severity ratio = clamp((actual - threshold) / threshold, 0, 1)。

    取 severity_feature 的第一条 condition 计算偏离度。
    severity_feature 不在 features → 0.0。
    threshold == 0 → 兜底 1.0（防除 0）。
    """
    feature_name = rule.get_severity_feature()
    if feature_name is None or feature_name not in features:
        return 0.0
    primary_cond = next(
        (c for c in rule.conditions if c.feature == feature_name),
        rule.conditions[0] if rule.conditions else None,
    )
    if primary_cond is None:
        return 0.0
    actual = features[feature_name]
    threshold = primary_cond.threshold
    if threshold == 0:
        return 1.0 if actual != 0 else 0.0
    ratio = abs(actual - threshold) / abs(threshold)
    return float(max(0.0, min(1.0, ratio)))


# ============================================================
# RuleEngine 主类
# ============================================================


class RuleEngine:
    """规则集合 + 互斥矩阵 + 评估。

    使用：
        engine = RuleEngine(rules=[rule_a, rule_b, ...])
        results = engine.diagnose(features, confidences)
        # results: list[RuleResult]，已应用互斥矩阵
    """

    def __init__(
        self,
        rules: list[Rule],
        *,
        engine_version: RuleEngineVersion = "v2.0",
    ) -> None:
        self._rules: list[Rule] = list(rules)
        self._engine_version: RuleEngineVersion = engine_version
        # 互斥矩阵预先构建：rule_name → set(被互斥的 rule_name)
        self._exclusion_map: dict[str, set[str]] = {}
        for r in self._rules:
            self._exclusion_map[r.name] = set(r.mutually_exclusive_with)
        # sanity：互斥关系应对称（rule_a 互斥 rule_b → rule_b 应互斥 rule_a）
        self._validate_mutual_exclusion_symmetry()

    @property
    def engine_version(self) -> RuleEngineVersion:
        return self._engine_version

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)  # defensive copy

    def diagnose(
        self,
        features: Mapping[str, float],
        confidences: Mapping[str, float] | None = None,
    ) -> list[RuleResult]:
        """诊断主入口。

        Args:
            features: 特征名 → 数值（pipeline features.py 输出）
            confidences: issue_type → confidence（M7-06 issue_confidence 输出）

        Returns:
            list[RuleResult]，已按 severity 降序 + 应用互斥矩阵
        """
        confidences = confidences or {}

        # 1. 评估所有规则
        triggered: list[RuleResult] = []
        for rule in self._rules:
            if not rule.evaluate(features):
                continue
            conf = confidences.get(rule.name, 1.0)
            if conf < rule.confidence_floor:
                continue
            severity = compute_severity(rule, features)
            payload = self._collect_payload(rule, features)
            triggered.append(
                RuleResult(
                    type=rule.name,
                    severity=severity,
                    confidence=conf,
                    rule_engine_version=rule.engine_version_tag,
                    display_name_key=rule.display_name_key,
                    payload=payload,
                )
            )

        # 2. 按 severity 降序排（同 severity → confidence 降序）
        triggered.sort(key=lambda r: (-r.severity, -r.confidence))

        # 3. 应用互斥矩阵：高 severity 优先；被抑制的丢弃
        kept: list[RuleResult] = []
        suppressed_types: set[str] = set()
        for result in triggered:
            if result.type in suppressed_types:
                continue
            kept.append(result)
            for ex_type in self._exclusion_map.get(result.type, set()):
                suppressed_types.add(ex_type)

        return kept

    def _collect_payload(
        self, rule: Rule, features: Mapping[str, float]
    ) -> dict[str, float]:
        """payload 仅包含规则用到的特征值，便于 i18n 文案插值且避免泄漏全集。"""
        return {
            cond.feature: features[cond.feature]
            for cond in rule.conditions
            if cond.feature in features
        }

    def _validate_mutual_exclusion_symmetry(self) -> None:
        """互斥关系应对称；启动时即抛错避免线上漂移。"""
        for rule_name, excluded in self._exclusion_map.items():
            for ex in excluded:
                # 允许互斥目标不在当前规则集（W29-W33 规则陆续加入时是常态）
                if ex not in self._exclusion_map:
                    continue
                if rule_name not in self._exclusion_map[ex]:
                    raise ValueError(
                        f"mutual_exclusion not symmetric: {rule_name} excludes {ex}, "
                        f"but {ex} does not exclude {rule_name}"
                    )


# ============================================================
# i18n 渲染（kickoff §3.4 占位）
# ============================================================


def render_i18n_key(
    key: str,
    payload: Mapping[str, Any],
    *,
    locale_dict: Mapping[str, str] | None = None,
) -> str:
    """从 locale_dict 取模板 + payload 插值。

    locale_dict 默认空 → 返回 `{key}` 本身（仅起跑期占位）。
    P2-W4 起 ``locales/zh_CN.json`` 与 starter rules 同步入库；调用方按需 load。

    模板格式：`你的{hip_dist}米偏离太大`
    """
    locale_dict = locale_dict or {}
    template = locale_dict.get(key, key)
    try:
        return template.format(**payload)
    except (KeyError, ValueError, IndexError):
        return template


# ============================================================
# YAML loader + locale loader（P2-W4）
# ============================================================

# yaml 在 import 时不强制：单测可以脱离 yaml 跑 RuleEngine 主体；
# 仅 ``load_rules_from_yaml`` 实际调用时再 import，避免装包顺序耦合。
RULES_DIR = Path(__file__).parent / "rules"
LOCALES_DIR = Path(__file__).parent / "locales"

# YAML 顶层允许字段（多于此集 → ValueError，避免拼写错被静默忽略）
_RULE_YAML_KEYS = {
    "name",
    "display_name_key",
    "severity_feature",
    "confidence_floor",
    "engine_version_tag",
    "mutually_exclusive_with",
    "conditions",
}
_CONDITION_YAML_KEYS = {"feature", "operator", "threshold"}


def _coerce_rule(raw: Mapping[str, Any]) -> Rule:
    """校验 + 转换单条 YAML rule → Rule dataclass。"""
    unknown = set(raw.keys()) - _RULE_YAML_KEYS
    if unknown:
        raise ValueError(f"rule 含未知字段：{sorted(unknown)}（rule={raw.get('name')!r}）")
    for required in ("name", "display_name_key", "conditions"):
        if required not in raw:
            raise ValueError(f"rule 缺字段 {required!r}（rule={raw.get('name')!r}）")
    conditions_raw = raw["conditions"]
    if not isinstance(conditions_raw, list) or not conditions_raw:
        raise ValueError(f"rule.conditions 必须为非空 list（rule={raw['name']!r}）")
    conditions: list[RuleCondition] = []
    for cond in conditions_raw:
        bad = set(cond.keys()) - _CONDITION_YAML_KEYS
        if bad:
            raise ValueError(f"condition 含未知字段 {sorted(bad)}（rule={raw['name']!r}）")
        if cond.get("operator") not in _OPERATORS:
            raise ValueError(
                f"condition.operator 非法：{cond.get('operator')!r}（rule={raw['name']!r}）"
            )
        conditions.append(
            RuleCondition(
                feature=str(cond["feature"]),
                operator=cond["operator"],
                threshold=float(cond["threshold"]),
            )
        )
    return Rule(
        name=str(raw["name"]),
        display_name_key=str(raw["display_name_key"]),
        conditions=tuple(conditions),
        severity_feature=raw.get("severity_feature"),
        mutually_exclusive_with=tuple(raw.get("mutually_exclusive_with", ()) or ()),
        confidence_floor=float(raw.get("confidence_floor", 0.0)),
        engine_version_tag=raw.get("engine_version_tag", "v2.0"),
    )


def load_rules_from_yaml(path: str | Path) -> list[Rule]:
    """从 YAML 文件读取规则定义。

    顶层结构::

        version: v2.0
        rules:
          - name: early_extension
            display_name_key: issues.early_extension.title
            conditions: [{feature: x, operator: ">", threshold: 0.15}]
            ...

    单测可直接传任意路径；线上 ``rule_engine_v2.py`` 默认走
    ``RULES_DIR / "v2_starter.yaml"``。
    """
    import yaml  # 局部 import：保留 pure-python 单测路径

    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML 顶层必须是 mapping：{path}")
    raw_rules = data.get("rules") or []
    if not isinstance(raw_rules, list):
        raise ValueError(f"YAML rules 必须是 list：{path}")
    return [_coerce_rule(r) for r in raw_rules]


def load_locale(locale_path: str | Path) -> dict[str, str]:
    """从 JSON 文件加载 locale 字典；仅顶层 key→string 模板。"""
    text = Path(locale_path).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"locale JSON 顶层必须是 mapping：{locale_path}")
    out: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(v, str):
            raise ValueError(f"locale 值必须为 string：key={k!r} path={locale_path}")
        out[str(k)] = v
    return out
