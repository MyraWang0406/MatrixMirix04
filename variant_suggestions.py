"""
基于 ElementScore + GateResult 的变体优化建议（结构化输出）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from element_scores import ElementScore
from eval_schemas import Variant, decompose_variant_to_element_tags
from explore_gate import ExploreGateResult
from simulate_metrics import SimulatedMetrics
from vertical_config import get_pool, get_why_now_pool, get_why_you_phrase_list, get_sell_point_options

# element_type -> 层级（策略/表达/行动/素材）
_LAYER_MAP = {
    "hook": "表达",
    "why_you": "策略",
    "why_now": "策略",
    "sell_point": "表达",
    "cta": "行动",
    "asset": "素材",
}

# element_type -> 改动字段
_FIELD_MAP = {
    "hook": "hook_type",
    "why_you": "why_you_bucket",
    "why_now": "why_now_trigger",
    "sell_point": "sell_point",
    "cta": "cta",
    "asset": "asset_var",
}

# change_field -> element_type
_CHANGE_FIELD_TO_ELEMENT = {
    "hook_type": "hook",
    "why_you_bucket": "why_you",
    "why_now_trigger": "why_now",
    "cta": "cta",
    "sell_point": "sell_point",
    "asset_var": "asset",
}


class VariantSuggestion(BaseModel):
    """处方单格式：原因 + 方向 + OFAAT 处方"""

    change_layer: str = Field(..., description="改动层级：策略/表达/行动/素材")
    changed_field: str = Field(..., description="改动字段：hook_type/why_you_bucket/why_now_trigger/cta")
    current_value: str = Field(..., description="当前取值")
    candidate_alternatives: list[str] = Field(
        default_factory=list,
        description="候选替代值（2-3 个）",
    )
    delta_desc: str = Field(
        default="",
        description="人类可读改动描述",
    )
    confidence_level: str = Field(
        default="low",
        description="low/medium/high，来自元素贡献",
    )
    expected_metric: str = Field(
        default="",
        description="预期改善指标：IPM / CPI / early_roas",
    )
    suggestion_type: str = Field(
        default="直接替换",
        description="复测方案 / 直接替换",
    )
    rationale: str = Field(
        default="",
        description="依据：引用 changed_field、delta_desc、置信度",
    )
    # 处方单扩展
    reason: str = Field(default="", description="触发原因（哪个窗口、哪个指标、相对 baseline 变化）")
    direction: str = Field(default="", description="改动方向（从候选池选哪类）")
    experiment_recipe: str = Field(
        default="",
        description="OFAAT 处方：一次只改一个字段，固定其余，生成 N 个变体",
    )
    target_os: str = Field(default="", description="端内修正时：target_os")
    sample_size: int = Field(default=0, description="含该元素的样本数（来自 element_scores）")


def _load_candidate_pool(config_path: Path | None = None) -> dict[str, Any]:
    """加载候选池配置"""
    if config_path is None:
        try:
            from path_config import SAMPLES_DIR
        except ImportError:
            SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
        config_path = SAMPLES_DIR / "candidate_pool.json"
    if not config_path.exists():
        return {"hook_type": [], "sell_point": [], "cta": [], "asset_var": {}}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_candidates(
    pool: dict[str, Any],
    element_type: str,
    current_value: str,
    n: int = 3,
    vertical: str = "casual_game",
) -> list[str]:
    """从候选池取 2-3 个替代值。优先使用 vertical_config 语料（严禁跨行业词）。"""
    if element_type == "why_you":
        lst = get_why_you_phrase_list(vertical)
    elif element_type == "why_now":
        lst = get_why_now_pool(vertical)
    elif element_type in ("hook", "sell_point", "cta"):
        key = "hook_type" if element_type == "hook" else element_type
        raw = get_pool(vertical, key) or []
        lst = [str(x) for x in raw] if isinstance(raw, list) else []
    else:
        lst = []
    if lst:
        others = [x for x in lst if str(x).strip() != str(current_value).strip()]
        return others[:n]
    if element_type == "asset":
        # asset: 从 vertical_config corpus.asset_var 或 pool 取
        parts = current_value.split("=", 1)
        if len(parts) == 2:
            k, v = parts[0], parts[1]
            sub = get_pool(vertical, "asset_var")
            if not isinstance(sub, dict):
                sub = pool.get("asset_var", {}) or {}
            lst = sub.get(k, []) if isinstance(sub, dict) else []
            if isinstance(lst, list):
                others = [x for x in lst if str(x).strip() != str(v).strip()]
            else:
                others = []
            return others[:n]
        return []
    return []


def _cross_os_consistent(
    element_type: str,
    element_value: str,
    variant_metrics: list[SimulatedMetrics | dict],
    variant_to_tags: dict[str, list[Any]],
) -> bool:
    """
    是否跨 OS 一致：含该元素的变体是否有 iOS 和 Android 双端数据。
    若有至少 2 个 OS 的样本，视为跨 OS 覆盖。
    """
    if not variant_metrics or not variant_to_tags:
        return False
    os_set = set()
    for m in variant_metrics:
        obj = SimulatedMetrics.model_validate(m) if isinstance(m, dict) else m
        tags = variant_to_tags.get(obj.variant_id, [])
        has_el = any(
            getattr(t, "element_type", "") == element_type and getattr(t, "element_value", "") == element_value
            for t in tags
        )
        if has_el:
            os_set.add(obj.os)
    return len(os_set) >= 2


def next_variant_suggestions(
    element_scores: list[ElementScore | dict],
    gate_result: ExploreGateResult | dict | None = None,
    *,
    max_suggestions: int = 3,
    candidate_pool_path: Path | None = None,
    variant_metrics: list[SimulatedMetrics | dict] | None = None,
    variant_to_tags: dict[str, list[Any]] | None = None,
    variants: list[Variant] | None = None,
    vertical: str = "casual_game",
    diagnosis: Any = None,
) -> list[VariantSuggestion]:
    """
    基于 diagnosis 处方 + ElementScore 生成可执行处方单。
    输出：reason + change_field + direction + experiment_recipe（OFAAT）。
    """
    pool = _load_candidate_pool(candidate_pool_path)
    vertical = (vertical or "casual_game").lower()
    scores = [
        ElementScore.model_validate(s) if isinstance(s, dict) else s
        for s in element_scores
    ]

    def _badness_score(s: ElementScore) -> float:
        return max(0, -s.avg_IPM_delta_vs_card_mean) + max(0, s.avg_CPI_delta_vs_card_mean)

    def _conf_rank(s: ElementScore) -> int:
        r = {"high": 2, "medium": 1, "low": 0}.get(getattr(s, "confidence_level", "low"), 0)
        return r

    if variant_to_tags is None and variants:
        variant_to_tags = {v.variant_id: decompose_variant_to_element_tags(v) for v in variants}
    variant_to_tags = variant_to_tags or {}

    # 优先使用 diagnosis 处方
    prescription_order: list[str] = []
    prescription_by_field: dict[str, Any] = {}
    if diagnosis and hasattr(diagnosis, "recommended_actions"):
        for p in diagnosis.recommended_actions:
            cf = getattr(p, "change_field", "") or ""
            if cf and cf not in prescription_order:
                prescription_order.append(cf)
                prescription_by_field[cf] = p

    # INCONCLUSIVE：仅补样本处方
    if diagnosis and getattr(diagnosis, "failure_type", "") == "INCONCLUSIVE":
        for p in getattr(diagnosis, "recommended_actions", []) or []:
            if getattr(p, "action", "") == "RESAMPLE":
                return [
                    VariantSuggestion(
                        change_layer="策略",
                        changed_field="",
                        current_value="保持原结构",
                        candidate_alternatives=[],
                        delta_desc="同结构复测，补足样本",
                        confidence_level="low",
                        expected_metric="",
                        suggestion_type="补样本",
                        rationale=getattr(p, "reason", ""),
                        reason=getattr(p, "reason", ""),
                        direction=getattr(p, "direction", "保持原结构不变"),
                        experiment_recipe=getattr(p, "experiment_recipe", ""),
                        target_os="",
                        sample_size=0,
                    ),
                ]
        return []

    # 按 prescription 或 element_scores 生成
    stable = [s for s in scores if s.stability_flag]
    underperform = [
        s for s in stable
        if s.avg_IPM_delta_vs_card_mean < 0 or s.avg_CPI_delta_vs_card_mean > 0
    ]
    underperform.sort(key=lambda x: (_conf_rank(x), _badness_score(x)), reverse=True)

    # 按 prescription_order 排序 element_types
    def _order_key(s: ElementScore) -> tuple:
        field = _FIELD_MAP.get(s.element_type, "sell_point")
        if s.element_type == "asset" and "=" in s.element_value:
            field = "asset_var"
        idx = prescription_order.index(field) if field in prescription_order else 99
        return (idx, -_conf_rank(s), -_badness_score(s))

    underperform.sort(key=_order_key)
    seen_types: set[str] = set()
    suggestions: list[VariantSuggestion] = []

    for s in underperform:
        if len(suggestions) >= max_suggestions:
            break
        field = _FIELD_MAP.get(s.element_type, "sell_point")
        if s.element_type == "asset" and "=" in s.element_value:
            field = "asset_var"
        if field in seen_types:
            continue
        seen_types.add(field)

        layer = _LAYER_MAP.get(s.element_type, "表达")
        current_val = s.element_value.split("=", 1)[-1] if s.element_type == "asset" and "=" in s.element_value else s.element_value

        candidates = _get_candidates(pool, s.element_type, s.element_value, n=3, vertical=vertical)
        if len(candidates) < 2 and candidates:
            candidates = candidates * 2
        candidates = list(dict.fromkeys(candidates))[:3]
        first_candidate = candidates[0] if candidates else "从候选池补充"

        conf = getattr(s, "confidence_level", "low")
        cross_os = getattr(s, "cross_os_consistency", "mixed")
        suggestion_type = "复测方案" if conf == "low" else "直接替换"

        pres = prescription_by_field.get(field)
        reason = getattr(pres, "reason", "") if pres else f"IPMΔ={s.avg_IPM_delta_vs_card_mean:+.1f} CPIΔ={s.avg_CPI_delta_vs_card_mean:+.2f}"
        direction = getattr(pres, "direction", "") if pres else f"从{field}候选池选"
        experiment_recipe = getattr(pres, "experiment_recipe", f"OFAAT：仅改{field}") if pres else f"OFAAT：仅改{field}"
        target_os = getattr(pres, "target_os", "") if pres else ""

        field_label = {"hook_type": "Hook", "sell_point": "卖点", "cta": "CTA", "asset_var": "素材", "why_you_bucket": "why_you", "why_now_trigger": "why_now"}.get(field, field)
        delta_desc = f"{field_label}: {current_val[:30]}{'…' if len(current_val) > 30 else ''} -> {first_candidate[:30]}{'…' if len(str(first_candidate)) > 30 else ''}"

        rationale_parts = [
            f"仅改 {field}",
            f"置信度={conf}",
            f"跨OS={cross_os}",
            f"样本n={s.sample_size}",
        ]
        if conf != "low":
            rationale_parts.append(f"IPMΔ={s.avg_IPM_delta_vs_card_mean:+.1f}")
            rationale_parts.append(f"CPIΔ={s.avg_CPI_delta_vs_card_mean:+.2f}")
        if diagnosis:
            ft = getattr(diagnosis, "failure_type", "") or ""
            ps = getattr(diagnosis, "primary_signal", "") or ""
            if ft and ps:
                rationale_parts.append(f"→诊断:{ft} ({ps})")
        rationale_parts.append(f"处方:{direction}")
        rationale = " | ".join(rationale_parts)

        if s.avg_IPM_delta_vs_card_mean < 0:
            expected_metric = "IPM"
        elif s.avg_CPI_delta_vs_card_mean > 0:
            expected_metric = "CPI"
        else:
            expected_metric = "early_roas"

        current_display = current_val[:60] + ("…" if len(current_val) > 60 else "")
        if conf == "low":
            current_display += " ⚠️ 样本不足"

        suggestions.append(VariantSuggestion(
            change_layer=layer,
            changed_field=field,
            current_value=current_display,
            candidate_alternatives=candidates if candidates else ["从候选池补充"],
            delta_desc=delta_desc,
            confidence_level=conf,
            expected_metric=expected_metric,
            suggestion_type=suggestion_type,
            rationale=rationale,
            reason=reason,
            direction=direction,
            experiment_recipe=experiment_recipe,
            target_os=target_os,
            sample_size=getattr(s, "sample_size", 0),
        ))

    # 若无 underperform 但有 prescription，生成纯处方建议
    if not suggestions and prescription_order:
        for cf in prescription_order[:max_suggestions]:
            pres = prescription_by_field.get(cf)
            if not pres or not cf:
                continue
            et = _CHANGE_FIELD_TO_ELEMENT.get(cf, "hook")
            candidates = _get_candidates(pool, et, "", n=3, vertical=vertical)
            suggestions.append(VariantSuggestion(
                change_layer=_LAYER_MAP.get(et, "表达"),
                changed_field=cf,
                current_value="当前值",
                candidate_alternatives=candidates or ["从候选池补充"],
                delta_desc=f"OFAAT：仅改{cf}",
                confidence_level="medium",
                expected_metric="IPM",
                suggestion_type="直接替换",
                rationale=getattr(pres, "reason", ""),
                reason=getattr(pres, "reason", ""),
                direction=getattr(pres, "direction", ""),
                experiment_recipe=getattr(pres, "experiment_recipe", ""),
                target_os=getattr(pres, "target_os", ""),
                sample_size=0,
            ))

    return suggestions
