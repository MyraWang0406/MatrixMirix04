"""
评测集设计：分层抽样 + 抗噪声 baseline。
评测集 = 结构卡片集合（非视频集合），具备可迁移性与可比性。
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from eval_schemas import StrategyCard

# 分层维度可选值
VERTICALS = ("casual_game", "ecommerce")
COUNTRIES = ("CN", "US", "")
SEGMENTS_DEFAULT = ("18-45岁休闲玩家", "18-30岁手游玩家", "价格敏感型", "品质党", "默认人群")
MOTIVATION_BUCKETS = ("省钱", "体验", "成就感", "爽感", "品质", "口碑", "其他")


def _seeded(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode()).hexdigest()
    return random.Random(int(h[:16], 16) % (2**32))


@dataclass
class StructureEvaluationSet:
    """评测集：一组 StrategyCard + 每层 baseline"""

    cards: list[StrategyCard] = field(default_factory=list)
    baseline_by_layer: dict[str, StrategyCard] = field(default_factory=dict)
    stratum_keys: list[str] = field(default_factory=list)


def _stratum_key(vertical: str, country: str, segment: str, mb: str) -> str:
    return f"{vertical}|{country or '_'}|{segment or '_'}|{mb}"


def _make_synthetic_card(
    card_id: str,
    vertical: str,
    country: str,
    segment: str,
    motivation_bucket: str,
    rng: random.Random,
) -> StrategyCard:
    """生成一张合成卡片（当 card_library 不足时）"""
    why_now_pool = [
        "新赛季刚开", "限时活动", "节日促销", "版本更新", "新手福利",
        "涨价预警", "大促来袭", "限时秒杀", "其他",
    ]
    wy_options = [
        ("price_advantage", "价格优势"), ("hero_easy", "上手快"), ("limited_offer", "限时优惠"),
        ("experience_upgrade", "体验升级"), ("other", "其他"),
    ]
    wy_key, wy_label = rng.choice(wy_options)
    wn = rng.choice(why_now_pool)
    return StrategyCard(
        card_id=card_id,
        version="1.0",
        vertical=vertical,
        country=country or "CN",
        os="all",
        objective="purchase" if vertical == "ecommerce" else "install",
        segment=segment or "默认人群",
        motivation_bucket=motivation_bucket,
        why_you_key=wy_key,
        why_you_label=wy_label,
        why_now_trigger=wn,
        root_cause_gap="",
    )


def sample_eval_set(
    target_n: int = 75,
    *,
    verticals: tuple[str, ...] = VERTICALS,
    countries: tuple[str, ...] = ("CN", ""),
    segments: tuple[str, ...] = SEGMENTS_DEFAULT,
    motivation_buckets: tuple[str, ...] = MOTIVATION_BUCKETS,
    card_pool: list[StrategyCard] | None = None,
    use_card_library: bool = True,
    seed: str = "evalset_sampler",
) -> StructureEvaluationSet:
    """
    分层抽样生成评测集。
    - 每层至少 1 张卡；配额不足则回退到「其他」桶
    - 若 card.os=all，则自动视为支持 iOS/Android 双端实验
    """
    rng = _seeded(seed)

    # 1. 构建层级与配额
    strata: list[tuple[str, str, str, str]] = []
    for v in verticals:
        for c in countries:
            for s in segments:
                for mb in motivation_buckets:
                    strata.append((v, c, s, mb))

    n_strata = len(strata)
    if target_n < n_strata:
        target_n = n_strata

    # 每层至少 1，剩余按层级数量比例分配
    base_per_stratum = 1
    remainder = target_n - n_strata * base_per_stratum
    if remainder < 0:
        remainder = 0
    extra_per = remainder // n_strata if n_strata else 0
    extra_rem = remainder % n_strata if n_strata else 0

    quota: dict[str, int] = {}
    for i, (v, c, s, mb) in enumerate(strata):
        key = _stratum_key(v, c, s, mb)
        q = base_per_stratum + extra_per + (1 if i < extra_rem else 0)
        quota[key] = q

    # 2. 加载 card_pool（优先用传入的，否则从 card_library）
    if card_pool is None and use_card_library:
        try:
            from card_library import load_cards
            card_pool = load_cards()
        except Exception:
            card_pool = []

    # 3. 从 card_pool 或合成卡片填充
    cards: list[StrategyCard] = []
    baseline_by_layer: dict[str, StrategyCard] = {}
    used_from_pool: set[str] = set()
    pool_by_stratum: dict[str, list[StrategyCard]] = {}

    if card_pool:
        for c in card_pool:
            v = getattr(c, "vertical", "") or ""
            cn = getattr(c, "country", "") or ""
            seg = getattr(c, "segment", "") or ""
            mb = getattr(c, "motivation_bucket", "") or "其他"
            key = _stratum_key(v, cn, seg, mb)
            pool_by_stratum.setdefault(key, []).append(c)

    card_idx = 0
    for (v, c, s, mb) in strata:
        key = _stratum_key(v, c, s, mb)
        q = quota.get(key, 1)
        pool = pool_by_stratum.get(key, [])
        for _ in range(q):
            if pool:
                cand = [x for x in pool if x.card_id not in used_from_pool]
                if cand:
                    chosen = rng.choice(cand)
                    used_from_pool.add(chosen.card_id)
                    cards.append(chosen)
                    if key not in baseline_by_layer:
                        baseline_by_layer[key] = chosen
                    continue
            card_idx += 1
            cid = f"sc_sampled_{card_idx:04d}"
            synthetic = _make_synthetic_card(cid, v, c, s, mb, rng)
            cards.append(synthetic)
            if key not in baseline_by_layer:
                baseline_by_layer[key] = synthetic

    return StructureEvaluationSet(
        cards=cards,
        baseline_by_layer=baseline_by_layer,
        stratum_keys=list(quota.keys()),
    )
