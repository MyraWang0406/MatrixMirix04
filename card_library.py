"""
Card Library：结构卡片资产化。
支持 load_cards / save_cards / filter_cards / bump_version。
渠道固定：Meta, TikTok, Google。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from eval_schemas import StrategyCard
except ImportError:
    StrategyCard = None

CARDS_DIR = Path(__file__).resolve().parent / "data" / "card_library"
CARDS_JSONL = CARDS_DIR / "cards.jsonl"
CARDS_INDEX = CARDS_DIR / "cards_index.json"
CHANNELS = ("Meta", "TikTok", "Google")


def _ensure_dir():
    CARDS_DIR.mkdir(parents=True, exist_ok=True)


def _card_to_index_entries(card: Any) -> dict[str, str]:
    return {
        "vertical": getattr(card, "vertical", "") or "",
        "country": getattr(card, "country", "") or "",
        "segment": getattr(card, "segment", "") or "",
        "motivation_bucket": getattr(card, "motivation_bucket", "") or "",
        "channel": getattr(card, "channel", "") or getattr(card, "source_channel", "") or "",
        "os": getattr(card, "os", "") or "",
    }


def _rebuild_index(cards: list) -> dict:
    indices = {"vertical": {}, "country": {}, "segment": {}, "motivation_bucket": {}, "channel": {}, "os": {}}
    card_ids = []
    for c in cards:
        cid = getattr(c, "card_id", str(c))
        card_ids.append(cid)
        for dim, val in _card_to_index_entries(c).items():
            v = val or "_empty"
            indices[dim].setdefault(v, []).append(cid)
    return {"version": 1, "updated_at": datetime.now().isoformat(), "indices": indices, "card_ids": list(dict.fromkeys(card_ids))}


def load_cards(path: Path | None = None) -> list:
    p = path or CARDS_JSONL
    if not p.exists():
        return []
    cards = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if StrategyCard:
                    cards.append(StrategyCard.model_validate(d))
                else:
                    cards.append(d)
            except Exception:
                continue
    return cards


def save_cards(cards: list, path: Path | None = None) -> None:
    _ensure_dir()
    p = path or CARDS_JSONL
    with open(p, "w", encoding="utf-8") as f:
        for c in cards:
            d = c.model_dump(mode="json") if hasattr(c, "model_dump") else c
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    idx_path = CARDS_INDEX
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(_rebuild_index(cards), f, ensure_ascii=False, indent=2)


def filter_cards(
    cards: list | None = None,
    *,
    vertical: str | None = None,
    country: str | None = None,
    segment: str | None = None,
    motivation_bucket: str | None = None,
    os_filter: str | None = None,
    channel: str | None = None,
) -> list:
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
        result = [c for c in result if (getattr(c, "motivation_bucket", "") or "").lower() == str(motivation_bucket).lower()]
    if os_filter:
        result = [c for c in result if ((getattr(c, "os", "") or "all").lower() == "all") or ((getattr(c, "os", "") or "").lower() == os_filter.lower())]
    if channel:
        result = [c for c in result if (getattr(c, "channel", "") or getattr(c, "source_channel", "") or "").lower() == channel.lower()]
    return result


def bump_version(card_id: str, cards: list | None = None):
    if cards is None:
        cards = load_cards()
    for c in cards:
        if getattr(c, "card_id", "") == card_id:
            d = c.model_dump() if hasattr(c, "model_dump") else dict(c)
            ver = d.get("version", "1.0")
            try:
                parts = str(ver).split(".")
                new_ver = f"{parts[0]}.{int(parts[1]) + 1}" if len(parts) > 1 else "1.1"
            except Exception:
                new_ver = "1.1"
            d["version"] = new_ver
            d["card_id"] = f"{card_id}_v{new_ver.replace('.', '_')}"
            new_card = StrategyCard.model_validate(d) if StrategyCard else d
            cards.append(new_card)
            save_cards(cards)
            return new_card
    return None


def add_card(card: Any) -> None:
    cards = [c for c in load_cards() if getattr(c, "card_id", "") != getattr(card, "card_id", "")]
    cards.append(card)
    save_cards(cards)


def get_card(card_id: str) -> Any | None:
    for c in load_cards():
        if getattr(c, "card_id", "") == card_id:
            return c
    return None
