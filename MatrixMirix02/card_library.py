"""
Card Library：结构卡片资产化。
支持 load_cards / save_cards / filter_cards / bump_version。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from eval_schemas import StrategyCard

CARDS_DIR = Path(__file__).resolve().parent / "data" / "cards"
CARDS_JSONL = CARDS_DIR / "cards.jsonl"
CARDS_INDEX = CARDS_DIR / "cards_index.json"


def _ensure_dir():
    CARDS_DIR.mkdir(parents=True, exist_ok=True)


def _card_to_index_entries(card: StrategyCard) -> dict[str, str]:
    """从卡片提取索引维度"""
    return {
        "vertical": getattr(card, "vertical", "") or "",
        "country": getattr(card, "country", "") or "",
        "segment": getattr(card, "segment", "") or "",
        "motivation_bucket": getattr(card, "motivation_bucket", "") or "",
    }


def _rebuild_index(cards: list[StrategyCard]) -> dict:
    """重建索引"""
    indices: dict[str, dict[str, list[str]]] = {
        "vertical": {},
        "country": {},
        "segment": {},
        "motivation_bucket": {},
    }
    card_ids: list[str] = []
    for c in cards:
        cid = c.card_id
        card_ids.append(cid)
        entries = _card_to_index_entries(c)
        for dim, val in entries.items():
            if not val:
                val = "_empty"
            indices[dim].setdefault(val, []).append(cid)
    return {
        "version": 1,
        "updated_at": datetime.now().isoformat(),
        "indices": indices,
        "card_ids": list(dict.fromkeys(card_ids)),
    }


def load_cards(path: Path | None = None) -> list[StrategyCard]:
    """加载所有卡片"""
    p = path or CARDS_JSONL
    if not p.exists():
        return []
    cards: list[StrategyCard] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                cards.append(StrategyCard.model_validate(d))
            except Exception:
                continue
    return cards


def save_cards(cards: list[StrategyCard], path: Path | None = None) -> None:
    """保存卡片到 JSONL 并重建索引"""
    _ensure_dir()
    p = path or CARDS_JSONL
    with open(p, "w", encoding="utf-8") as f:
        for c in cards:
            d = c.model_dump(mode="json")
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    index_path = path.parent / "cards_index.json" if path else CARDS_INDEX
    idx = _rebuild_index(cards)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def filter_cards(
    cards: list[StrategyCard] | None = None,
    *,
    vertical: str | None = None,
    country: str | None = None,
    segment: str | None = None,
    motivation_bucket: str | None = None,
    os_filter: str | None = None,
) -> list[StrategyCard]:
    """
    按 vertical/country/segment/motivation_bucket/os 筛选卡片。
    os_filter: "iOS" | "Android" | "all" | None（不筛选）
    card.os=all 时视为双端均可。
    """
    if cards is None:
        cards = load_cards()
    result = cards
    if vertical:
        result = [c for c in result if (getattr(c, "vertical", "") or "").lower() == vertical.lower()]
    if country:
        result = [c for c in result if (getattr(c, "country", "") or "").lower() == country.lower()]
    if segment:
        result = [c for c in result if segment in (getattr(c, "segment", "") or "")]
    if motivation_bucket:
        mb = getattr(c, "motivation_bucket", "") or ""
        result = [c for c in result if mb == motivation_bucket]
    if os_filter:
        result = [
            c for c in result
            if ((getattr(c, "os", "") or "all").lower() == "all")
            or ((getattr(c, "os", "") or "").lower() == os_filter.lower())
        ]
    return result


def bump_version(card_id: str, cards: list[StrategyCard] | None = None) -> StrategyCard | None:
    """
    版本升级：保留历史，复制为 card_id_v{next} 并递增 version。
    返回新卡片；原卡片保留在库中（历史版本）。
    """
    if cards is None:
        cards = load_cards()
    for c in cards:
        if c.card_id == card_id:
            d = c.model_dump()
            ver = d.get("version", "1.0")
            try:
                major, minor = ver.split(".")
                new_ver = f"{major}.{int(minor) + 1}"
            except Exception:
                new_ver = "1.1"
            d["version"] = new_ver
            d["card_id"] = f"{card_id}_v{new_ver.replace('.', '_')}"
            new_card = StrategyCard.model_validate(d)
            cards.append(new_card)
            save_cards(cards)
            return new_card
    return None


def add_card(card: StrategyCard) -> None:
    """新增一张卡片到库"""
    cards = load_cards()
    cards = [c for c in cards if c.card_id != card.card_id]
    cards.append(card)
    save_cards(cards)


def get_card(card_id: str) -> StrategyCard | None:
    """按 card_id 获取卡片"""
    cards = load_cards()
    for c in cards:
        if c.card_id == card_id:
            return c
    return None
