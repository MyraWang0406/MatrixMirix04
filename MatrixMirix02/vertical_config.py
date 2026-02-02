"""
Vertical 语料决定器：ecommerce / casual_game 两套词库，切换后内容完全不同。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from path_config import SAMPLES_DIR
except ImportError:
    SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
CONFIG_PATH = SAMPLES_DIR / "vertical_config.json"

_config: dict[str, Any] | None = None
_VERTICALS = ("ecommerce", "casual_game")


def _normalize_vertical(v: str) -> str:
    """统一为 ecommerce 或 casual_game"""
    v = (v or "casual_game").lower().strip()
    if v in _VERTICALS:
        return v
    return "casual_game"


def load_vertical_config() -> dict[str, Any]:
    global _config
    if _config is None:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                _config = json.load(f)
        else:
            _config = {}
    return _config


def get_corpus(vertical: str) -> dict[str, Any]:
    """获取该 vertical 的完整语料库（动机桶/why_you/why_now/sell_point/cta/hook/segment/asset_var/root_cause_gap）"""
    cfg = load_vertical_config()
    corpus = cfg.get("corpus", {})
    v = _normalize_vertical(vertical)
    return dict(corpus.get(v, {}))


def get_pool(vertical: str, key: str) -> list[str] | list[dict] | dict[str, list[str]]:
    """获取指定候选池。key: motivation_bucket/why_you_bucket/why_now_trigger/sell_point/cta/hook_type/segment"""
    c = get_corpus(vertical)
    val = c.get(key)
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return val
    return []


def get_why_you_options(vertical: str) -> list[tuple[str, str]]:
    """获取 Why you 选项：[(key, label), ...]，用于评测集生成等。词库扩展时只需在 config 增加 {key, label}，eval 不崩溃。"""
    c = get_corpus(vertical)
    wy = c.get("why_you_bucket") or []
    result: list[tuple[str, str]] = []
    for item in wy:
        if isinstance(item, dict):
            k = item.get("key", "other")
            lbl = item.get("label", "其他")
            result.append((str(k), str(lbl)))
        elif isinstance(item, str):
            result.append((item, item))
    return result if result else [("other", "其他")]


def get_sample_strategy_card(vertical: str) -> dict[str, Any]:
    """获取该 vertical 的示例 StrategyCard（字段值全部来自该 vertical 候选池，严禁跨行业词）"""
    cfg = load_vertical_config()
    samples = cfg.get("sample_strategy_card", {})
    v = _normalize_vertical(vertical)
    return dict(samples.get(v, {}))


def get_root_cause_gap(vertical: str, index: int = 0) -> str:
    """获取 root_cause_gap 文案。电商：怕踩雷/怕错过/比价成本；游戏：上手/爽点/福利"""
    c = get_corpus(vertical)
    gaps = c.get("root_cause_gap", [])
    if isinstance(gaps, list) and gaps:
        return gaps[index % len(gaps)]
    return ""


def get_why_you_examples(vertical: str) -> dict[str, list[str]]:
    """获取 Why you 示例话术库（按 label 为 key）"""
    cfg = load_vertical_config()
    examples = cfg.get("why_you_examples", {})
    v = _normalize_vertical(vertical)
    if v in examples:
        return dict(examples[v])
    c = get_corpus(v)
    wy = c.get("why_you_bucket", [])
    sp = c.get("sell_point", [])
    labels = []
    for item in wy:
        if isinstance(item, dict):
            labels.append(item.get("label", ""))
        elif isinstance(item, str):
            labels.append(item)
    return {lb: (sp[:3] if sp else []) for lb in labels if lb} if labels else {}


def get_why_now_pool(vertical: str) -> list[str]:
    """获取 Why now 触发器候选池"""
    return list(get_pool(vertical, "why_now_trigger") or [])


def get_metric_weights(vertical: str, os: str = "") -> dict[str, float]:
    """获取指标权重"""
    cfg = load_vertical_config()
    weights = cfg.get("metric_weights", {})
    v = _normalize_vertical(vertical)
    w = dict(weights.get(v, {"ipm": 0.4, "cpi": 0.35, "early_roas": 0.25, "ctr": 0.0}))
    if "ctr" not in w:
        w["ctr"] = w.get("ipm", 0.4) * 0.5
    return w


def get_why_now_strong_stimulus_penalty(vertical: str) -> float:
    """why_now 强刺激风险扣分"""
    cfg = load_vertical_config()
    rules = cfg.get("risk_rules", {})
    v = _normalize_vertical(vertical)
    r = rules.get(v, {})
    return float(r.get("why_now_strong_stimulus_penalty", 3.0))


def get_why_now_strong_triggers(vertical: str) -> list[str]:
    """why_now 强刺激触发器列表"""
    cfg = load_vertical_config()
    rules = cfg.get("risk_rules", {})
    v = _normalize_vertical(vertical)
    r = rules.get(v, {})
    return list(r.get("why_now_strong_triggers", []))


def get_why_you_phrase_list(vertical: str = "casual_game") -> list[str]:
    """给 variant_suggestions 用的 why_you 短语列表"""
    c = get_corpus(vertical) or {}
    phrases = c.get("why_you_phrases") or {}
    if isinstance(phrases, dict):
        out = []
        for v in phrases.values() if phrases else []:
            if isinstance(v, list):
                out.extend(x for x in v if isinstance(x, str))
        if out:
            return out
    return list(get_pool(vertical, "why_you_bucket") or []) or ["省钱", "体验更好", "更省时间"]


def get_sell_point_options(vertical: str = "casual_game") -> list[str]:
    """给 variant_suggestions 用的 sell_point 列表"""
    v = get_pool(vertical, "sell_point")
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []


def use_refund_risk(vertical: str) -> bool:
    """是否使用退款风险字段（ecommerce）"""
    cfg = load_vertical_config()
    weights = cfg.get("metric_weights", {})
    v = _normalize_vertical(vertical)
    w = weights.get(v, {})
    return bool(w.get("use_refund_risk", False))


def early_roas_as_proxy(vertical: str) -> bool:
    """early_roas 是否作为 proxy"""
    cfg = load_vertical_config()
    weights = cfg.get("metric_weights", {})
    v = _normalize_vertical(vertical)
    w = weights.get(v, {})
    return bool(w.get("early_roas_as_proxy", True))
