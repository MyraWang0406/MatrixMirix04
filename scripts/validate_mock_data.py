#!/usr/bin/env python3
"""
校验 mock JSON 数据：遍历 samples/、configs/、data/ 中的 JSON，输出缺字段统计。
运行后不抛异常退出（返回码 0），只打印报告。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保能导入 eval_schemas
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "MatrixMirix02") not in sys.path:
    sys.path.insert(0, str(ROOT / "MatrixMirix02"))

from pydantic import ValidationError

try:
    from eval_schemas import StrategyCard, Variant
except ImportError:
    StrategyCard = Variant = None


def _is_card_json(d: dict) -> bool:
    return "card_id" in d or ("vertical" in d and "motivation_bucket" in d)


def _is_variant_json(d: dict) -> bool:
    return "variant_id" in d and "parent_card_id" in d


def _load_json_or_jsonl(p: Path):
    """加载 JSON 或 JSONL"""
    with open(p, "r", encoding="utf-8") as f:
        if p.suffix == ".jsonl":
            return [json.loads(line) for line in f if line.strip()]
        return json.load(f)


def check_file(p: Path) -> dict:
    """检查单个文件，返回统计"""
    result = {"path": str(p), "cards_ok": 0, "cards_fail": 0, "variants_ok": 0, "variants_fail": 0, "errors": []}
    try:
        data = _load_json_or_jsonl(p)
    except Exception as e:
        result["errors"].append(f"解析失败: {e}")
        return result

    if isinstance(data, list):
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            if _is_card_json(item) and StrategyCard:
                try:
                    StrategyCard.model_validate(item)
                    result["cards_ok"] += 1
                except ValidationError as e:
                    result["cards_fail"] += 1
                    missing = [err.get("loc", ()) for err in e.errors()]
                    result["errors"].append(f"[{i}] card 缺字段: {missing}")
            elif _is_variant_json(item) and Variant:
                try:
                    Variant.model_validate(item)
                    result["variants_ok"] += 1
                except ValidationError as e:
                    result["variants_fail"] += 1
                    missing = [err.get("loc", ()) for err in e.errors()]
                    result["errors"].append(f"[{i}] variant 缺字段: {missing}")
    elif isinstance(data, dict):
        if _is_card_json(data) and StrategyCard:
            try:
                StrategyCard.model_validate(data)
                result["cards_ok"] = 1
            except ValidationError as e:
                result["cards_fail"] = 1
                missing = [err.get("loc", ()) for err in e.errors()]
                result["errors"].append(f"card 缺字段: {missing}")
    return result


def main():
    dirs = [
        ROOT / "samples",
        ROOT / "configs",
        ROOT / "data" / "card_library",
    ]
    total_why_now_missing = 0
    total_fail = 0

    print("=== Mock 数据校验报告 ===\n")

    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.json")) + sorted(d.rglob("*.jsonl")):
            if p.name.startswith("."):
                continue
            res = check_file(p)
            if res["cards_fail"] or res["variants_fail"] or res["errors"]:
                total_fail += res["cards_fail"] + res["variants_fail"]
                for err in res["errors"]:
                    if "why_now" in str(err).lower():
                        total_why_now_missing += 1
                print(f"📄 {res['path']}")
                print(f"   cards: ok={res['cards_ok']} fail={res['cards_fail']}")
                print(f"   variants: ok={res['variants_ok']} fail={res['variants_fail']}")
                for e in res["errors"][:5]:
                    print(f"   - {e}")
                if len(res["errors"]) > 5:
                    print(f"   ... 共 {len(res['errors'])} 条错误")
                print()

    print("--- 汇总 ---")
    print(f"why_now_trigger 相关缺失: {total_why_now_missing}")
    print(f"总校验失败数: {total_fail}")
    print("\n运行完成（退出码 0）")
    sys.exit(0)


if __name__ == "__main__":
    main()
