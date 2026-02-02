"""
评测集批量模拟数据生成：50-100 张 StrategyCard，每张卡状态流转与 Explore/Validate 汇总。
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

from eval_schemas import StrategyCard, Variant

# Literal 兜底：词库扩展时若值不在允许列表，自动替换为"其他"
_MOTIVATION_ALLOWED = frozenset(["省钱", "体验", "社交", "胜负欲", "成就感", "收集", "爽感", "品质", "口碑", "其他"])
_WHY_NOW_ALLOWED = frozenset([
    "新赛季刚开", "限时活动", "节日促销", "版本更新", "热度上升",
    "竞品疲软", "节点冲刺", "用户召回",
    "涨价预警", "大促来袭", "限时秒杀", "满减活动", "库存告急", "新品首发", "会员日特惠",
    "新手福利", "周末双倍", "赛季末冲刺", "新英雄上线",
    "其他",
])
_WHY_YOU_KEYS_ALLOWED = frozenset([
    "price_advantage", "limited_offer", "quality_guarantee", "word_of_mouth", "need_based",
    "experience_upgrade", "hero_easy", "season_reward", "rank_easier", "social_showcase", "catharsis", "other",
])


def _normalize_card_fields(
    mb: str,
    wy_key: str,
    wy_label: str,
    wn: str,
) -> tuple[str, str, str, str]:
    """归一化 StrategyCard 字段，防止 ValidationError。返回 (mb, wy_key, wy_label, wn)。"""
    mb_norm = mb if mb in _MOTIVATION_ALLOWED else "其他"
    wy_key_norm = wy_key if wy_key in _WHY_YOU_KEYS_ALLOWED else "other"
    wy_label_norm = wy_label if wy_label else "其他"
    wn_norm = wn if wn in _WHY_NOW_ALLOWED else "其他"
    return mb_norm, wy_key_norm, wy_label_norm, wn_norm


from explore_gate import evaluate_explore_gate
from ofaat_generator import generate_ofaat_variants
from simulate_metrics import simulate_metrics
from validate_gate import WindowMetrics, evaluate_validate_gate
from vertical_config import get_corpus, get_why_you_options

# 状态：未测 -> 探索中 -> 进验证 -> 可放量
CARD_STATUSES = ("未测", "探索中", "进验证", "可放量")


def _seeded(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode()).hexdigest()
    return random.Random(int(h[:16], 16) % (2**32))


@dataclass
class CardEvalRecord:
    """单张卡评测记录"""
    card: StrategyCard
    card_score: float
    status: str  # 未测/探索中/进验证/可放量
    variants: list[Variant]
    explore_ios: Any
    explore_android: Any
    validate_result: Any | None = None
    window_metrics: list[WindowMetrics] = field(default_factory=list)
    expand_segment_metrics: WindowMetrics | None = None


def generate_eval_set(
    n_cards: int = 75,
    variants_per_card: int = 12,
    *,
    status_dist: dict[str, float] | None = None,
) -> list[CardEvalRecord]:
    """
    生成评测集：n_cards 张 StrategyCard，每张至少 variants_per_card 个变体。
    状态分布：未测/探索中/进验证/可放量，默认各约 25%。
    """
    status_dist = status_dist or {
        "未测": 0.25, "探索中": 0.30, "进验证": 0.25, "可放量": 0.20,
    }
    rng = _seeded("eval_set_v1")
    records: list[CardEvalRecord] = []

    for i in range(n_cards):
        cid = f"sc_{i+1:03d}"
        seed = f"card_{cid}"
        r = _seeded(seed)

        vert = "casual_game" if r.random() < 0.7 else "ecommerce"
        corp = get_corpus(vert)
        mb_pool = corp.get("motivation_bucket") or ["成就感", "爽感", "其他"]
        wy_options = get_why_you_options(vert)
        wn_pool = corp.get("why_now_trigger") or ["新赛季刚开", "限时活动", "其他"]
        seg_pool = corp.get("segment") or ["18-30岁手游玩家"]
        mb_raw = r.choice(mb_pool) if mb_pool else "其他"
        wy_key_raw, wy_label_raw = r.choice(wy_options) if wy_options else ("other", "其他")
        wn_raw = r.choice(wn_pool) if wn_pool else "其他"
        seg = r.choice(seg_pool) if seg_pool else "默认人群"

        mb, wy_key, wy_label, wn = _normalize_card_fields(mb_raw, wy_key_raw, wy_label_raw, wn_raw)

        obj = "purchase" if vert == "ecommerce" else "install"
        card = StrategyCard(
            card_id=cid,
            version="1.0",
            vertical=vert,
            country="CN",
            os="all",
            objective=obj,
            segment=seg,
            motivation_bucket=mb,
            why_you_key=wy_key,
            why_you_label=wy_label,
            why_now_trigger=wn,
            root_cause_gap="",
        )

        # 生成变体（语料来自 vertical）
        hooks = corp.get("hook_type") or ["冲突/悬念", "利益前置", "社交/炫耀"]
        sells = corp.get("sell_point") or ["新赛季冲分黄金期", "赛季皮肤免费领"]
        ctas = corp.get("cta") or ["立即下载", "领福利", "马上开玩"]
        vs = generate_ofaat_variants(
            cid,
            list(hooks)[:8],
            list(sells)[:8],
            list(ctas)[:5],
            n=variants_per_card,
        )

        # 模拟 metrics
        metrics = []
        metrics.append(simulate_metrics(vs[0], "iOS", baseline=True, motivation_bucket=mb, vertical=vert))
        metrics.append(simulate_metrics(vs[0], "Android", baseline=True, motivation_bucket=mb, vertical=vert))
        for v in vs[1:]:
            metrics.append(simulate_metrics(v, "iOS", baseline=False, motivation_bucket=mb, vertical=vert))
            metrics.append(simulate_metrics(v, "Android", baseline=False, motivation_bucket=mb, vertical=vert))

        # Explore Gate
        baseline_list = [m for m in metrics if m.baseline]
        variant_list = [m for m in metrics if not m.baseline]
        ctx = {"country": "CN", "objective": "install", "segment": seg, "motivation_bucket": mb}
        exp_ios = evaluate_explore_gate(variant_list, baseline_list, context={**ctx, "os": "iOS"})
        exp_android = evaluate_explore_gate(variant_list, baseline_list, context={**ctx, "os": "Android"})

        # card_score 模拟：基于 eligible 数量与随机
        eligible = list(dict.fromkeys((exp_ios.eligible_variants or []) + (exp_android.eligible_variants or [])))
        base_score = min(100.0, 40.0 + len(eligible) * 4.0 + r.uniform(0, 25))
        card_score = round(base_score, 1)

        # 状态
        rv = rng.random()
        cum = 0.0
        status = "未测"
        for s, p in status_dist.items():
            cum += p
            if rv <= cum:
                status = s
                break

        # 进验证/可放量 时生成 Validate 数据
        window_metrics: list[WindowMetrics] = []
        expand_metrics: WindowMetrics | None = None
        validate_result = None

        if status in ("进验证", "可放量"):
            w1_ipm = metrics[0].ipm * (0.95 + r.uniform(0, 0.1))
            w1_cpi = metrics[0].cpi * (0.98 + r.uniform(0, 0.06))
            w1_roas = metrics[0].early_roas * (0.9 + r.uniform(0, 0.2))
            w2_ipm = w1_ipm * (0.85 + r.uniform(0, 0.2))
            w2_cpi = w1_cpi * (1.0 + r.uniform(-0.05, 0.15))
            w2_roas = w1_roas * (0.95 + r.uniform(-0.1, 0.2))
            imp1 = 50000
            imp2 = 52000
            inst1 = max(100, int(imp1 * w1_ipm / 1000))
            inst2 = max(100, int(imp2 * w2_ipm / 1000))
            window_metrics = [
                WindowMetrics(window_id="window_1", impressions=imp1, clicks=800, installs=inst1,
                              spend=6000, early_events=1200, early_revenue=480, ipm=round(w1_ipm, 2), cpi=round(w1_cpi, 2), early_roas=round(w1_roas, 4)),
                WindowMetrics(window_id="window_2", impressions=imp2, clicks=840, installs=inst2,
                              spend=6240, early_events=1250, early_revenue=500, ipm=round(w2_ipm, 2), cpi=round(w2_cpi, 2), early_roas=round(w2_roas, 4)),
            ]
            # 轻扩人群：通常略差
            exp_ipm = w2_ipm * (0.80 + r.uniform(0, 0.15))
            exp_cpi = w2_cpi * (1.0 + r.uniform(0, 0.2))
            exp_roas = w2_roas * (0.9 + r.uniform(-0.1, 0.15))
            exp_inst = max(50, int(20000 * exp_ipm / 1000))
            expand_metrics = WindowMetrics(
                window_id="expand_segment", impressions=20000, clicks=320, installs=exp_inst,
                spend=2400, early_events=400, early_revenue=160, ipm=round(exp_ipm, 2), cpi=round(exp_cpi, 2), early_roas=round(exp_roas, 4),
            )
            validate_result = evaluate_validate_gate(window_metrics, expand_metrics)

        records.append(CardEvalRecord(
            card=card,
            card_score=card_score,
            status=status,
            variants=vs,
            explore_ios=exp_ios,
            explore_android=exp_android,
            validate_result=validate_result,
            window_metrics=window_metrics,
            expand_segment_metrics=expand_metrics,
        ))

    return records
