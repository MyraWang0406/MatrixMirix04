#!/usr/bin/env python3
"""
冒烟验收：验证模块导入、路径解析、最小决策链路可跑通。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "MatrixMirix02"
if PKG.exists():
    _p = str(PKG.resolve())
    if _p not in sys.path:
        sys.path.insert(0, _p)

def main():
    print("=== Smoke Check ===\n")
    errs = []

    # 1. 导入入口模块
    print("1. 导入模块...")
    try:
        import element_scores
        import eval_schemas
        import decision_summary
        import diagnosis
    except Exception as e:
        errs.append(f"导入失败: {e}")
        print(f"   ✗ {e}")
        sys.exit(1)
    print("   ✓ 导入成功")

    # 2. 打印模块 __file__（验证未命中错误目录）
    print("\n2. 模块路径自检:")
    for name in ("element_scores", "eval_schemas", "decision_summary", "diagnosis"):
        m = sys.modules.get(name)
        if m and hasattr(m, "__file__") and m.__file__:
            p = m.__file__
            ok = "MatrixMirix02" in p or "matrixmirix02" in p.lower()
            print(f"   {name}: {p} {'✓' if ok else '⚠'}")
        else:
            print(f"   {name}: (unknown)")

    # 3. 加载 example_creative_card 并跑通最小链路
    print("\n3. 加载 samples 并跑通最小链路...")
    samples = ROOT / "samples"
    if not samples.exists():
        samples = ROOT.parent / "samples"
    card_path = samples / "example_creative_card.json"
    if not card_path.exists():
        card_path = samples / "eval_strategy_card_casual_game.json"
    if not card_path.exists():
        print("   ⚠ 未找到 card JSON，跳过链路测试")
        return 0

    with open(card_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    card = eval_schemas.StrategyCard.model_validate(raw)
    print(f"   ✓ StrategyCard 加载: {card.card_id}")

    # 模拟决策 summary
    from eval_schemas import Variant
    from simulate_metrics import simulate_metrics

    variant_path = samples / "eval_variants_casual_game.json"
    if not variant_path.exists():
        variant_path = samples / "eval_variants.json"
    if variant_path.exists():
        with open(variant_path, "r", encoding="utf-8") as f:
            vs = [Variant.model_validate(v) for v in json.load(f)]
        vs = [v.model_copy(update={"parent_card_id": card.card_id}) for v in vs]
        mb = getattr(card, "motivation_bucket", "成就感") or "成就感"
        metrics = []
        metrics.append(simulate_metrics(vs[0], "iOS", baseline=True, motivation_bucket=mb, vertical="casual_game"))
        metrics.append(simulate_metrics(vs[0], "Android", baseline=True, motivation_bucket=mb, vertical="casual_game"))
        for v in vs[1:]:
            metrics.append(simulate_metrics(v, "iOS", baseline=False, motivation_bucket=mb, vertical="casual_game"))
            metrics.append(simulate_metrics(v, "Android", baseline=False, motivation_bucket=mb, vertical="casual_game"))
        from explore_gate import evaluate_explore_gate
        from validate_gate import WindowMetrics, evaluate_validate_gate
        baseline_list = [m for m in metrics if m.baseline]
        variant_list = [m for m in metrics if not m.baseline]
        ctx = {"country": "CN", "objective": "install", "segment": card.segment, "motivation_bucket": mb}
        exp_ios = evaluate_explore_gate(variant_list, baseline_list, context={**ctx, "os": "iOS"})
        exp_android = evaluate_explore_gate(variant_list, baseline_list, context={**ctx, "os": "Android"})
        windowed = [
            WindowMetrics(window_id="window_1", impressions=50000, clicks=800, installs=2000, spend=6000, early_events=1200, early_revenue=480, ipm=40, cpi=3, early_roas=0.08),
            WindowMetrics(window_id="window_2", impressions=55000, clicks=880, installs=2090, spend=6270, early_events=1250, early_revenue=500, ipm=38, cpi=3, early_roas=0.08),
        ]
        val_res = evaluate_validate_gate(windowed)
        diag = diagnosis.diagnose(exp_ios=exp_ios, exp_android=exp_android, validate_result=val_res, metrics=metrics)
        summary = decision_summary.compute_decision_summary({
            "explore_ios": exp_ios, "explore_android": exp_android,
            "validate_result": val_res, "metrics": metrics,
        })
        print(f"   ✓ 决策 summary: {summary.get('status_text', '-')} | diagnosis: {diag.failure_type}")
    else:
        print("   ⚠ 未找到 variants JSON，跳过决策链路")

    print("\n=== Smoke Check 完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
