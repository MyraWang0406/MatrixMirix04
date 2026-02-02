"""
评测集设计：分层抽样 + 抗噪 baseline。
评测集 = 结构卡片集合，可迁移、抗噪、跨国家/人群/渠道可对比。
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "default_evalset_config.json"

# 英文 motivation_bucket -> 场景+动机（商品具体化）
_MB_MAP = {
    "deal_discount": "帐篷·雨季将至·防雨耐用", "compare": "便携收纳·周末出游·一键搞定", "gift": "宠物肖像油画·送礼怕不合心意·更匹配我",
    "pain_relief": "老年人备忘录·健忘怕遗漏·更省事", "convenience": "便携收纳·周末出游·一键搞定", "social_proof": "车载装备·假期自驾·省空间耐用",
    "premium_quality": "帐篷·雨季将至·防雨耐用", "boredom": "消消乐·通勤碎片·连击爽感", "competition": "贪吃蛇·无聊专注·经典怀旧",
    "collection": "合成类·换季解压·关卡有层次", "social": "Gossip Harbor·朋友都在玩·社交归属", "immersion": "消消乐·通勤碎片·连击爽感", "reward": "闯关类·新赛季开启·道具丰富",
}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _seeded(seed: str) -> random.Random:
    h = hashlib.sha256(seed.encode()).hexdigest()
    return random.Random(int(h[:16], 16) % (2**32))


@dataclass
class StructureEvaluationSet:
    """评测集：一组 StrategyCard + 每层 baseline"""

    cards: list = field(default_factory=list)
    baseline_by_stratum: dict[str, Any] = field(default_factory=dict)
    stratum_keys: list[str] = field(default_factory=list)


def _stratum_key(v: str, ch: str, c: str, s: str, o: str, mb: str) -> str:
    return f"{v}|{ch}|{c}|{s}|{o}|{mb}"


def _make_card(
    card_id: str,
    vertical: str,
    channel: str,
    country: str,
    segment: str,
    os_val: str,
    motivation_bucket: str,
    rng: random.Random,
) -> Any:
    """合成一张 StrategyCard"""
    try:
        from eval_schemas import StrategyCard
    except ImportError:
        return {"card_id": card_id, "vertical": vertical, "channel": channel, "country": country, "segment": segment, "os": os_val, "motivation_bucket": motivation_bucket}

    mb_cn = _MB_MAP.get(motivation_bucket, "其他")
    why_now = ["限时稀缺", "节点事件", "机会出现", "其他"][rng.randint(0, 3)]
    why_you = ["更省钱", "更省事", "更好体验", "其他"][rng.randint(0, 3)]
    return StrategyCard(
        card_id=card_id,
        version="1.0",
        vertical=vertical,
        country=country,
        channel=channel,
        os=os_val,
        objective="purchase" if vertical == "ecommerce" else "install",
        segment=segment,
        motivation_bucket=mb_cn,
        why_you_bucket=why_you,
        why_you_phrase="",
        why_now_trigger_bucket=why_now,
        why_now_phrase="",
        why_now_trigger=why_now,
        root_cause_gap="",
    )


def sample_structure_evalset(
    N: int = 80,
    *,
    config_path: Path | None = None,
    card_pool: list | None = None,
    use_card_library: bool = True,
    seed: str = "evalset",
) -> StructureEvaluationSet:
    """
    分层抽样生成评测集。
    每层至少 1 张；不足则回退到 country=US / segment=new / motivation_bucket=deal_discount。
    每个分层单元指定 baseline。
    """
    cfg = _load_config() if config_path is None else json.loads((config_path if isinstance(config_path, Path) else Path(config_path)).read_text(encoding="utf-8"))
    rng = _seeded(seed)

    vert_ratio = cfg.get("vertical", {"ecommerce": 0.7, "casual_game": 0.3})
    ch_ratio = cfg.get("channel", {"Meta": 0.45, "TikTok": 0.35, "Google": 0.2})
    countries = cfg.get("country", ["US", "JP", "KR", "TH", "VN", "BR"])
    os_ratio = cfg.get("os", {"Android": 0.6, "iOS": 0.4})
    seg_ratio = cfg.get("segment", {"new": 0.6, "returning": 0.25, "retargeting": 0.15})
    mb_cfg = cfg.get("motivation_bucket", {})
    mb_ecom = mb_cfg.get("ecommerce", ["deal_discount", "compare", "gift", "pain_relief", "social_proof"])
    mb_game = mb_cfg.get("game", ["boredom", "competition", "collection", "reward"])
    fallback = cfg.get("fallback", {"country": "US", "segment": "new", "motivation_bucket": "deal_discount"})

    # 构建分层单元：vertical × channel × country（约 2×3×6=36 层，可生成 50–100 张）
    strata: list[tuple[str, str, str, str, str, str]] = []
    seg_list = list(seg_ratio.keys())
    os_list = list(os_ratio.keys())
    for v in vert_ratio:
        for ch in ch_ratio:
            for c in countries:
                s = rng.choice(seg_list) if seg_list else "new"
                o = rng.choices(os_list, weights=[os_ratio.get(x, 0.5) for x in os_list], k=1)[0] if os_list else "Android"
                mb = rng.choice(mb_ecom) if v == "ecommerce" else rng.choice(mb_game)
                strata.append((v, ch, c, s, o, mb))
    n_strata = len(strata)
    if N < n_strata:
        N = n_strata

    base_per = 1
    remainder = N - n_strata * base_per
    extra_per = remainder // n_strata if n_strata else 0
    extra_rem = remainder % n_strata if n_strata else 0

    quota: dict[str, int] = {}
    for i, t in enumerate(strata):
        key = _stratum_key(*t)
        quota[key] = base_per + extra_per + (1 if i < extra_rem else 0)

    if card_pool is None and use_card_library:
        try:
            from card_library import load_cards
            card_pool = load_cards()
        except Exception:
            card_pool = []

    pool_by_key: dict[str, list] = {}
    for c in card_pool or []:
        v = getattr(c, "vertical", "") or ""
        ch = getattr(c, "channel", "") or getattr(c, "source_channel", "") or ""
        co = getattr(c, "country", "") or ""
        seg = getattr(c, "segment", "") or ""
        o = getattr(c, "os", "") or "all"
        mb = getattr(c, "motivation_bucket", "") or ""
        mb_en = next((k for k, vv in _MB_MAP.items() if vv == mb), "deal_discount")
        key = _stratum_key(v, ch or "Meta", co or "US", seg or "new", o, mb_en)
        pool_by_key.setdefault(key, []).append(c)

    cards: list = []
    baseline_by_stratum: dict[str, Any] = {}
    used: set = set()
    idx = 0

    for (v, ch, c, s, o, mb) in strata:
        key = _stratum_key(v, ch, c, s, o, mb)
        q = quota.get(key, 1)
        pool = pool_by_key.get(key, [])

        for _ in range(q):
            if pool:
                cand = [x for x in pool if getattr(x, "card_id", id(x)) not in used]
                if cand:
                    chosen = rng.choice(cand)
                    used.add(getattr(chosen, "card_id", id(chosen)))
                    cards.append(chosen)
                    if key not in baseline_by_stratum:
                        baseline_by_stratum[key] = chosen
                    continue

            idx += 1
            cid = f"sc_{v[:3]}_{idx:04d}"
            synth = _make_card(cid, v, ch, c, s, o, mb, rng)
            cards.append(synth)
            if key not in baseline_by_stratum:
                baseline_by_stratum[key] = synth

    return StructureEvaluationSet(cards=cards, baseline_by_stratum=baseline_by_stratum, stratum_keys=list(quota.keys()))
