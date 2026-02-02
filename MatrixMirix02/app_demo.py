"""
【废弃】请使用根目录 MatrixMirix02/app_demo.py 作为唯一入口。
本文件仅作备份，请勿直接运行。
"""
from __future__ import annotations

import sys
if __name__ == "__main__":
    print("ERROR: 请使用根目录 app_demo.py：cd MatrixMirix02 && streamlit run app_demo.py")
    sys.exit(1)

import json
from collections import defaultdict
from pathlib import Path

import streamlit as st

# 仅使用本地模块，无 openrouter、无 API
from element_scores import ElementScore, compute_element_scores
from eval_schemas import StrategyCard, Variant
from eval_set_generator import CardEvalRecord, generate_eval_set
from explore_gate import evaluate_explore_gate
from ofaat_generator import generate_ofaat_variants
from scoring_eval import compute_card_score, compute_variant_score
from simulate_metrics import SimulatedMetrics, simulate_metrics
from vertical_config import (
    get_corpus,
    get_why_now_pool,
    get_why_now_strong_stimulus_penalty,
    get_why_now_strong_triggers,
    get_why_you_examples,
)
from validate_gate import WindowMetrics, evaluate_validate_gate
from variant_suggestions import next_variant_suggestions

st.set_page_config(page_title="决策看板", layout="wide", initial_sidebar_state="collapsed")

# 样式：标题蓝色水波、联系作者、电梯导航、响应式
st.markdown("""
<style>
/* 标题区：深浅蓝渐变 + 水波感 */
.title-banner {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 25%, #3d7ab5 50%, #2d5a87 75%, #1e3a5f 100%);
    background-size: 200% 200%;
    animation: wave 8s ease infinite;
    padding: 1rem 1.5rem;
    margin: -1rem -1rem 1rem -1rem;
    border-radius: 0 0 12px 12px;
}
@keyframes wave {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
.title-banner h1 { color: #fff !important; margin: 0 !important; font-weight: 600; }
/* 联系作者：右下角黑底白字 */
.contact-footer {
    position: fixed; bottom: 0; right: 0;
    background: #1a1a1a; color: #fff;
    padding: 0.4rem 0.8rem; font-size: 0.85rem;
    border-radius: 8px 0 0 0;
}
.contact-footer a { color: #fff; text-decoration: none; }
/* 电梯导航 */
.nav-pill { padding: 0.3rem 0.6rem; margin: 0.2rem 0; border-radius: 6px; font-size: 0.9rem; }
.nav-pill:hover { background: #e8f4fc; }
/* 表格横向滚动 */
[data-testid="stDataFrame"], .stDataFrame { overflow-x: auto !important; max-width: 100%; }
/* 蓝色系，无红色 */
button[kind="primary"] { background-color: #2563eb !important; }
/* 结构卡摘要：字号与标题一致，避免过大 */
[data-testid="stMetric"] { font-size: 1rem !important; }
[data-testid="stMetric"] label { font-size: 0.85rem !important; }
[data-testid="stMetric"] [style*="font-size"] { font-size: 1rem !important; }
/* 决策看板置顶：标题栏滚动时保持可见 */
.title-banner { position: sticky !important; top: 0 !important; z-index: 100 !important; }
/* 电梯导航左边悬空 */
/* 电梯导航左边悬空：2列布局的首列 */
[data-testid="stHorizontalBlock"]:has(> div:nth-child(2):nth-last-child(2)) > div:first-child {
  position: sticky !important; top: 140px !important; align-self: flex-start !important; z-index: 10 !important;
}
@media (max-width: 768px) {
    .main .block-container { padding: 1rem !important; max-width: 100% !important; }
}
</style>
""", unsafe_allow_html=True)

try:
    from path_config import SAMPLES_DIR
except ImportError:
    SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

# 窗口 ID 到投放语境文案的映射
# 窗口 ID → 投放语境文案（tooltip 见明细表下方 caption）
WINDOW_LABELS = {
    "window_1": "首测窗口",
    "window_2": "跨天复测",
    "expand_segment": "轻扩人群",
}


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").replace("，", ",").split(",") if x.strip()]


def load_mock_data(
    variants: list[Variant] | None = None,
    vertical_override: str | None = None,
    motivation_bucket_override: str | None = None,
):
    """加载 StrategyCard、Variants，并生成所有模拟数据。vertical 决定语料：ecommerce/casual_game 各自独立词库。"""
    vert = (vertical_override or "casual_game").lower()
    if vert not in ("ecommerce", "casual_game"):
        vert = "casual_game"

    # 语料决定器：按 vertical 加载对应卡片与变体（严禁跨行业词）
    card_path = SAMPLES_DIR / f"eval_strategy_card_{vert}.json"
    variant_path = SAMPLES_DIR / f"eval_variants_{vert}.json"
    if not card_path.exists():
        card_path = SAMPLES_DIR / "eval_strategy_card.json"
    if not variant_path.exists():
        variant_path = SAMPLES_DIR / "eval_variants.json"

    with open(card_path, "r", encoding="utf-8") as f:
        card = StrategyCard.model_validate(json.load(f))
    # 强制 vertical 与 root_cause_gap 来自配置
    from vertical_config import get_sample_strategy_card, get_root_cause_gap
    sample = get_sample_strategy_card(vert)
    if sample:
        card = card.model_copy(update={
            "vertical": vert,
            "motivation_bucket": motivation_bucket_override or sample.get("motivation_bucket") or card.motivation_bucket,
            "why_you_key": sample.get("why_you_key") or card.why_you_key,
            "why_you_label": sample.get("why_you_label") or card.why_you_label,
            "why_now_trigger": sample.get("why_now_trigger") or card.why_now_trigger,
            "segment": sample.get("segment") or card.segment,
            "objective": sample.get("objective") or card.objective,
            "root_cause_gap": sample.get("root_cause_gap") or get_root_cause_gap(vert) or card.root_cause_gap,
        })

    if variants is None:
        with open(variant_path, "r", encoding="utf-8") as f:
            variants = [Variant.model_validate(v) for v in json.load(f)]
        # 确保 parent_card_id 与 card 一致
        variants = [
            v.model_copy(update={"parent_card_id": card.card_id}) if v.parent_card_id != card.card_id else v
            for v in variants
        ]

    # 模拟 metrics：v001 baseline，v002/v003 测试（motivation_bucket + vertical 影响分布）
    mb = getattr(card, "motivation_bucket", "") or ("省钱" if vert == "ecommerce" else "成就感")
    metrics = []
    metrics.append(simulate_metrics(variants[0], "iOS", baseline=True, motivation_bucket=mb, vertical=vert))
    metrics.append(simulate_metrics(variants[0], "Android", baseline=True, motivation_bucket=mb, vertical=vert))
    for v in variants[1:]:
        metrics.append(simulate_metrics(v, "iOS", baseline=False, motivation_bucket=mb, vertical=vert))
        metrics.append(simulate_metrics(v, "Android", baseline=False, motivation_bucket=mb, vertical=vert))

    # Explore Gate（iOS + Android 各一次，context 含 motivation_bucket）
    baseline_list = [m for m in metrics if m.baseline]
    variant_list = [m for m in metrics if not m.baseline]
    obj = (card.objective or "").strip() or ("purchase" if vert == "ecommerce" else "install")
    ctx_base = {"country": "CN", "objective": obj, "segment": card.segment, "motivation_bucket": mb}
    explore_ios = evaluate_explore_gate(
        variant_list, baseline_list,
        context={**ctx_base, "os": "iOS"},
    )
    explore_android = evaluate_explore_gate(
        variant_list, baseline_list,
        context={**ctx_base, "os": "Android"},
    )

    # Element 贡献
    element_scores = compute_element_scores(variant_metrics=metrics, variants=variants)

    # 下一步建议（结构化）
    from eval_schemas import decompose_variant_to_element_tags
    variant_to_tags = {v.variant_id: decompose_variant_to_element_tags(v) for v in variants}
    suggestions = next_variant_suggestions(
        element_scores,
        gate_result=explore_android,
        max_suggestions=3,
        variant_metrics=metrics,
        variant_to_tags=variant_to_tags,
        variants=variants,
        vertical=vert,
    )

    # Validate Gate（模拟多窗口 + 轻扩）
    windowed = [
        WindowMetrics(window_id="window_1", impressions=50000, clicks=800, installs=2000,
                      spend=6000, early_events=1200, early_revenue=480,
                      ipm=40.0, cpi=3.0, early_roas=0.08),
        WindowMetrics(window_id="window_2", impressions=55000, clicks=880, installs=2090,
                      spend=6270, early_events=1250, early_revenue=500,
                      ipm=38.0, cpi=3.0, early_roas=0.08),
    ]
    light_exp = WindowMetrics(
        window_id="expand_segment", impressions=20000, clicks=288, installs=720,
        spend=2160, early_events=430, early_revenue=172,
        ipm=36.0, cpi=3.0, early_roas=0.08,
    )
    validate_result = evaluate_validate_gate(windowed, light_exp)

    # variant_score：每行 metrics 一个分，按 OS 归一化（使用 vertical 配置权重）
    variant_scores_by_row: dict[tuple[str, str], float] = {}
    for m in metrics:
        cohort = [x for x in metrics if x.os == m.os]
        variant_scores_by_row[(m.variant_id, m.os)] = compute_variant_score(
            m, cohort, os=m.os, vertical=vert
        )
    # 按 variant_id 聚合成单分（跨 OS 取均值）
    by_vid: dict[str, list[float]] = defaultdict(list)
    for (vid, _), s in variant_scores_by_row.items():
        by_vid[vid].append(s)
    variant_scores_agg = {vid: sum(s) / len(s) for vid, s in by_vid.items()}

    # card_score：取 eligible 的 topK 均值 + 惩罚（按 vertical 配置风险规则）
    eligible_all = list(dict.fromkeys(
        (explore_ios.eligible_variants or []) + (explore_android.eligible_variants or [])
    ))
    stab_penalty = 5.0 if validate_result.validate_status == "FAIL" else 0.0
    why_now_penalty = 0.0
    strong_triggers = get_why_now_strong_triggers(vert)
    wn_trigger = getattr(card, "why_now_trigger", "") or ""
    if wn_trigger in strong_triggers:
        why_now_penalty = get_why_now_strong_stimulus_penalty(vert)
    elif any("why now" in n.lower() or "虚高" in n or "强刺激" in n for n in validate_result.risk_notes):
        why_now_penalty = get_why_now_strong_stimulus_penalty(vert) * 0.5
    card_score_result = compute_card_score(
        eligible_variants=eligible_all,
        variant_scores=variant_scores_agg,
        top_k=5,
        stability_penalty=stab_penalty,
        why_now_strong_stimulus_penalty=why_now_penalty,
    )

    return {
        "card": card,
        "vertical": vert,
        "variants": variants,
        "metrics": metrics,
        "explore_ios": explore_ios,
        "explore_android": explore_android,
        "element_scores": element_scores,
        "suggestions": suggestions,
        "validate_result": validate_result,
        "variant_scores_by_row": variant_scores_by_row,
        "card_score_result": card_score_result,
    }


def render_eval_set_view():
    """评测集视图：结构评测集、探索评测集、验证评测集"""
    st.markdown('<div class="title-banner"><h1>评测集 (Eval Set)</h1></div>', unsafe_allow_html=True)
    # 主区域顶部：卡片数量 + 生成按钮
    col_n, col_btn, _ = st.columns([1, 1, 4])
    with col_n:
        n_cards = st.number_input("卡片数量 (n_cards)", min_value=50, max_value=100, value=75, step=5, key="eval_n_cards")
    with col_btn:
        if st.button("生成 / 重新生成评测集", type="primary", key="eval_gen_btn"):
            with st.spinner("生成评测集中..."):
                records = generate_eval_set(n_cards=n_cards, variants_per_card=12)
                st.session_state["eval_set_records"] = records
            st.rerun()

    records: list[CardEvalRecord] = st.session_state.get("eval_set_records", [])
    if not records:
        st.warning("暂无数据，请点击「生成 / 重新生成评测集」")
        return

    tab1, tab2, tab3 = st.tabs([
        "结构评测集 (Structure Eval Set)",
        "探索评测集 (Explore Eval Set)",
        "验证评测集 (Validate Eval Set)",
    ])

    with tab1:
        st.subheader("结构评测集：卡片列表 (card_score + 状态)")
        status_filter = st.multiselect("筛选状态", ["未测", "探索中", "进验证", "可放量"], default=["未测", "探索中", "进验证", "可放量"])
        filtered = [r for r in records if r.status in status_filter]
        rows = [
            {
                "卡片 (card_id)": r.card.card_id,
                "分数 (card_score)": f"{r.card_score:.1f}",
                "状态 (status)": r.status,
                "动机桶 (motivation_bucket)": r.card.motivation_bucket,
                "垂直 (vertical)": r.card.vertical,
                "人群 (segment)": (r.card.segment[:20] + "…" if len(r.card.segment) > 20 else r.card.segment),
            }
            for r in filtered
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption(f"共 {len(filtered)} 张卡 | 未测:{sum(1 for r in records if r.status=='未测')} 探索中:{sum(1 for r in records if r.status=='探索中')} 进验证:{sum(1 for r in records if r.status=='进验证')} 可放量:{sum(1 for r in records if r.status=='可放量')}")

    with tab2:
        st.subheader("探索评测集：每张卡 Explore 结果汇总")
        rows = []
        for r in records:
            e_ios = r.explore_ios
            e_android = r.explore_android
            eligible_ios = len(e_ios.eligible_variants or [])
            eligible_android = len(e_android.eligible_variants or [])
            total_var = len(r.variants) * 2  # iOS + Android 各算
            pass_ios = e_ios.gate_status == "PASS"
            pass_android = e_android.gate_status == "PASS"
            rows.append({
                "卡片 (card_id)": r.card.card_id,
                "状态 (status)": r.status,
                "变体数 (variants)": len(r.variants),
                "iOS 通过数 (eligible)": eligible_ios,
                "Android 通过数 (eligible)": eligible_android,
                "iOS 门禁 (gate)": "✓" if pass_ios else "✗",
                "Android 门禁 (gate)": "✓" if pass_android else "✗",
            })
        st.dataframe(rows, width="stretch", hide_index=True)

    with tab3:
        st.subheader("验证评测集：通过探索的卡的 Validate 明细")
        validate_records = [r for r in records if r.status in ("进验证", "可放量") and r.validate_result]
        if not validate_records:
            st.info("暂无进入验证阶段的卡片")
        else:
            for r in validate_records[:20]:  # 展示前 20 张
                with st.expander(f"{r.card.card_id} | 状态:{r.status} | Validate:{r.validate_result.validate_status}"):
                    if r.validate_result.detail_rows:
                        detail_data = [
                            {"窗口": WINDOW_LABELS.get(row.window_id, row.window_id), "IPM": f"{row.ipm:.2f}", "CPI": f"{row.cpi:.2f}", "early_ROAS": f"{row.early_roas:.2%}"}
                            for row in r.validate_result.detail_rows
                        ]
                        st.dataframe(detail_data, width="stretch", hide_index=True)
                    sm = r.validate_result.stability_metrics
                    st.caption(f"波动(ipm_cv)={sm.ipm_cv:.2%} 回撤(ipm_drop)={sm.ipm_drop_pct:.1f}% CPI涨幅={sm.cpi_increase_pct:.1f}% 学习反复(learning_iter)={sm.learning_iterations}")
                    for n in r.validate_result.risk_notes:
                        st.caption(f"• {n}")
            if len(validate_records) > 20:
                st.caption(f"仅展示前 20 张，共 {len(validate_records)} 张进入验证")


def _multiselect_with_actions(label: str, options: list[str], key: str, default_all: bool = True):
    """多选下拉，支持全选/清空。返回选中列表。"""
    if not options:
        return []
    widget_key = f"{key}_ms"
    default = options if default_all else options[:3]
    col_sel, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("全选", key=f"{key}_all"):
            st.session_state[widget_key] = options
            st.rerun()
        if st.button("清空", key=f"{key}_clear"):
            st.session_state[widget_key] = []
            st.rerun()
    with col_sel:
        selected = st.multiselect(
            label,
            options=options,
            default=st.session_state.get(widget_key, default),
            key=widget_key,
            placeholder="选 1 项以上…",
        )
    return selected


def main():
    st.markdown(
        '<div class="contact-footer">联系作者 <a href="mailto:myrawzm0406@163.com">myrawzm0406@163.com</a></div>',
        unsafe_allow_html=True,
    )

    def _on_vertical_change():
        st.session_state["use_generated"] = False
        st.session_state["generated_variants"] = None

    # 1. 决策看板置顶：顶部控制栏 + 蓝色标题（滚动时标题栏保持可见）
    nav_col1, nav_col2, nav_col3, nav_col4, _ = st.columns([1, 1, 1, 1, 4])
    with nav_col1:
        view = st.radio("视图", ["决策看板", "评测集"], label_visibility="collapsed", horizontal=True, key="view_radio")
    with nav_col2:
        vert_idx = st.selectbox("行业", ["休闲游戏", "电商"], index=0, key="vertical_select", on_change=_on_vertical_change)
        vertical_choice = "casual_game" if vert_idx == "休闲游戏" else "ecommerce"
    with nav_col3:
        help_clicked = st.button("❓ 帮助")
    banner_title = "评测集 (Eval Set)" if view == "评测集" else "决策看板 (Decision Board)"
    st.markdown(f'<div class="title-banner"><h1>{banner_title}</h1></div>', unsafe_allow_html=True)
    if help_clicked:
        st.session_state["show_help"] = not st.session_state.get("show_help", False)
    if st.session_state.get("show_help"):
        st.info("选择「决策看板」或「评测集」。决策看板：顶部选 hook/卖点/CTA 后点「生成并评测」。游戏/电商切换后语料自动切换。")

    if view == "评测集":
        render_eval_set_view()
        return

    if "use_generated" not in st.session_state:
        st.session_state["use_generated"] = False
    if "generated_variants" not in st.session_state:
        st.session_state["generated_variants"] = None

    # ----- 布局：左侧电梯导航 + 右侧主内容 -----
    SECTIONS = [
        ("1 结构卡片", "sec-1"),
        ("2 实验对照表", "sec-2"),
        ("3 门禁状态", "sec-3"),
        ("4 元素贡献", "sec-4"),
        ("5 变体建议", "sec-5"),
    ]
    nav_section = st.session_state.get("nav_section", "sec-1")
    col_nav, col_main = st.columns([1, 6])
    with col_nav:
        st.caption("📌 电梯导航")
        for label, sid in SECTIONS:
            if st.button(label, key=f"nav_{sid}", use_container_width=True):
                st.session_state["nav_section"] = sid
                st.rerun()

    with col_main:
        corp = get_corpus(vertical_choice)
        hook_opts = corp.get("hook_type") or ["反差(Before/After)", "冲突", "结果先行", "痛点", "爽点"]
        sell_opts = corp.get("sell_point") or ["示例卖点"]
        cta_opts = corp.get("cta") or ["立即下载", "现在试试", "立即下单", "立刻试玩"]
        mb_opts = corp.get("motivation_bucket") or ["成就感", "爽感", "其他"]

        with st.container():
            f1, f2, f3, f4, f5, f6, f7 = st.columns([2, 2, 2, 1.2, 0.8, 1, 1])
            with f1:
                hooks = _multiselect_with_actions("Hook", hook_opts, f"filter_hook_{vertical_choice}")
            with f2:
                sells = _multiselect_with_actions("卖点", sell_opts, f"filter_sell_{vertical_choice}")
            with f3:
                ctas = _multiselect_with_actions("CTA", cta_opts, f"filter_cta_{vertical_choice}")
            with f4:
                mb_selected = st.selectbox("动机桶", mb_opts, key="filter_mb")
            with f5:
                n_gen = st.number_input("N", min_value=1, max_value=24, value=12, step=1, help="生成变体数量")
            with f6:
                if st.button("生成并评测", type="primary"):
                    if not hooks or not sells or not ctas:
                        st.error("请至少各选 1 项 hook、卖点、CTA")
                    else:
                        card_path = SAMPLES_DIR / f"eval_strategy_card_{vertical_choice}.json"
                        if not card_path.exists():
                            card_path = SAMPLES_DIR / "eval_strategy_card.json"
                        with open(card_path, "r", encoding="utf-8") as f:
                            card = StrategyCard.model_validate(json.load(f))
                        asset_pool = corp.get("asset_var") or {}
                        vs = generate_ofaat_variants(
                            card.card_id,
                            hooks,
                            sells,
                            ctas,
                            n=n_gen,
                            asset_pool=asset_pool,
                        )
                        st.session_state["generated_variants"] = vs
                        st.session_state["use_generated"] = True
                        st.success(f"已生成 {len(vs)} 个变体")
                        st.rerun()
            with f7:
                if st.session_state["use_generated"] and st.button("恢复示例"):
                    st.session_state["use_generated"] = False
                    st.session_state["generated_variants"] = None
                    st.rerun()

        variants_arg = st.session_state["generated_variants"] if st.session_state["use_generated"] else None
        data = load_mock_data(
            variants=variants_arg,
            vertical_override=vertical_choice,
            motivation_bucket_override=mb_selected,
        )
        card = data["card"]
        metrics = data["metrics"]
        variants = data["variants"]
        vert = data.get("vertical", getattr(card, "vertical", "casual_game") or "casual_game")

        st.markdown('<span id="sec-1"></span>', unsafe_allow_html=True)
        st.subheader("1️⃣ 结构卡片摘要")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("动机桶", getattr(card, "motivation_bucket", "-") or "成就感")
        with c2:
            st.metric("Why you", card.why_you_label)
        with c3:
            st.metric("Why now", card.why_now_trigger)
        with c4:
            st.metric("人群", card.segment[:18] + "…" if len(card.segment) > 18 else card.segment)
        with c5:
            st.metric("行业", "休闲游戏" if vert == "casual_game" else "电商")
        with c6:
            st.metric("投放目标", card.objective)
        st.caption(f"国家/OS: {card.country or '-'} / {card.os or '-'}")
        if vert == "ecommerce":
            st.caption("电商：early_roas 权重大，含退款风险")
        if card.root_cause_gap:
            st.info(card.root_cause_gap)

        st.divider()
        st.markdown('<span id="sec-2"></span>', unsafe_allow_html=True)
        st.subheader("2️⃣ 实验对照表 (OFAAT)")

        var_map = {v.variant_id: v for v in variants}
        explore_by_os = {"iOS": data["explore_ios"], "Android": data["explore_android"]}
        scores_by_row = data.get("variant_scores_by_row", {})

        rows = []
        for m in metrics:
            v = var_map.get(m.variant_id)
            exp = explore_by_os.get(m.os)
            status = exp.variant_details.get(m.variant_id, "-") if exp else "-"
            score_val = scores_by_row.get((m.variant_id, m.os), 0.0)
            if m.baseline:
                exp_var, delta = "—", "基线"
            else:
                exp_var = getattr(v, "changed_field", "") or "—"
                d = getattr(v, "delta_desc", "") or "—"
                delta = d[:45] + ("…" if len(d) > 45 else "")
            row = {
                "实验ID": m.variant_id,
                "基线": "✓" if m.baseline else "",
                "实验变量": exp_var,
                "改动（只改一处）": delta,
                "OS": m.os,
                "分数": f"{score_val:.1f}",
                "Hook": v.hook_type if v else "-",
                "卖点": (v.sell_point[:24] + "…" if v and len(v.sell_point) > 24 else (v.sell_point if v else "-")),
                "CTA": v.cta_type if v else "-",
                "曝光": f"{m.impressions:,}",
                "安装": m.installs,
                "花费": f"${m.spend:,.0f}",
                "千次曝光安装数(IPM)": f"{m.ipm:.1f}",
                "CPI": f"${m.cpi:.2f}",
                "early_ROAS": f"{m.early_roas:.2%}",
                "门禁": status,
            }
            if vert == "ecommerce":
                row["退款风险"] = f"{getattr(m, 'refund_risk', 0):.2%}"
                row["转化代理"] = f"{getattr(m, 'conversion_proxy', 0):.2%}"
                row["下单代理"] = f"{getattr(m, 'order_proxy', 0):.2%}"
            rows.append(row)

        st.caption("💡 实验ID：同一实验在 iOS/Android 各有一行结果")
        st.dataframe(rows, width="stretch", hide_index=True)

        st.divider()
        st.markdown('<span id="sec-3"></span>', unsafe_allow_html=True)
        st.subheader("3️⃣ 门禁状态与结论")

        card_score_result = data.get("card_score_result", {})
        card_score_val = card_score_result.get("card_score", 0.0)
        st.metric("卡片总分", f"{card_score_val:.1f}")

        t1, t2 = st.tabs(["探索门禁", "验证门禁"])

        with t1:
            baseline_list = [m for m in metrics if m.baseline]
            baseline_by_os = {m.os: m for m in baseline_list}

            exp_ios, exp_android = data["explore_ios"], data["explore_android"]
            os_tabs = st.tabs(["iOS", "Android"])
            for tab, os_name, exp in [(os_tabs[0], "iOS", exp_ios), (os_tabs[1], "Android", exp_android)]:
                with tab:
                    status_color = "🟢" if exp.gate_status == "PASS" else "🔴" if exp.gate_status == "FAIL" else "🟡"
                    st.write(f"**{os_name}** {status_color} `{exp.gate_status}`")
                    bl = baseline_by_os.get(os_name)
                    if bl:
                        variant_metrics_os = [m for m in metrics if m.os == os_name and not m.baseline]
                        gate_rows = []
                        for m in variant_metrics_os:
                            better = sum([m.ctr > bl.ctr, m.ipm > bl.ipm, m.cpi < bl.cpi])
                            beat_baseline = "是" if better >= 2 else "否"
                            status = exp.variant_details.get(m.variant_id, "-")
                            gate_rows.append({
                                "实验ID": m.variant_id,
                                "千次曝光安装数(IPM)": f"{m.ipm:.1f}",
                                "CPI": f"${m.cpi:.2f}",
                                "early_ROAS": f"{m.early_roas:.2%}",
                                "≥2指标超baseline": beat_baseline,
                                "结论": status,
                            })
                        if gate_rows:
                            st.dataframe(gate_rows, width="stretch", hide_index=True)
                    with st.expander("📋 门禁说明与详情"):
                        if exp.eligible_variants:
                            st.success(f"通过: {', '.join(exp.eligible_variants)}")
                        for r in exp.reasons:
                            st.caption(f"• {r}")

        with t2:
            v = data["validate_result"]
            val_ios, val_android = st.tabs(["iOS", "Android"])
            for vt in [val_ios, val_android]:
                with vt:
                    st.write("**Validate**", "🟢 PASS" if v.validate_status == "PASS" else "🔴 FAIL")

                    if getattr(v, "detail_rows", None) and v.detail_rows:
                        st.caption("**明细表**（窗口含义见 tooltip）")
                        detail_data = []
                        for r in v.detail_rows:
                            wl = WINDOW_LABELS.get(r.window_id, r.window_id)
                            detail_data.append({
                                "窗口": wl,
                                "千次曝光安装数(IPM)": f"{r.ipm:.2f}",
                                "CPI": f"{r.cpi:.2f}",
                                "early_ROAS": f"{r.early_roas:.2%}",
                                "曝光": r.impressions,
                                "花费": f"${r.spend:,.0f}",
                            })
                        st.dataframe(detail_data, width="stretch", hide_index=True)
                        st.caption("💡 首测窗口=首次测试投放；跨天复测=跨天验证稳定性；轻扩人群=轻度扩圈后表现")

                    if getattr(v, "stability_metrics", None):
                        sm = v.stability_metrics
                        with st.expander("📋 稳定性指标"):
                            st.write(f"波动: {sm.ipm_cv:.2%} | 回撤: {sm.ipm_drop_pct:.1f}% | CPI涨幅: {sm.cpi_increase_pct:.1f}% | 学习反复: {sm.learning_iterations}")

                    with st.expander("📋 风险提示与放量建议"):
                        for n in v.risk_notes:
                            st.caption(f"• {n}")
                        for k, val in v.scale_recommendation.items():
                            st.write(f"**{k}**: {val}")

        st.divider()
        st.markdown('<span id="sec-4"></span>', unsafe_allow_html=True)
        st.subheader("4️⃣ 元素级贡献表")

        scores = data["element_scores"]
        et_labels = {"hook": "Hook", "why_you": "Why you", "why_now": "Why now", "sell_point": "卖点", "sell_point_copy": "卖点话术", "cta": "CTA"}
        for et in ["hook", "why_you", "why_now", "sell_point", "sell_point_copy", "cta"]:
            subset = [s for s in scores if s.element_type == et]
            if not subset:
                continue
            st.write(f"**{et_labels.get(et, et)}**")
            for s in subset:
                conf = getattr(s, "confidence_level", "low")
                cross_os = getattr(s, "cross_os_consistency", "mixed")

                if conf == "low":
                    st.caption(f"⚠️ 「{s.element_value[:36]}{'…' if len(s.element_value) > 36 else ''}」 样本不足(n={s.sample_size})，建议复测 | 跨OS={cross_os}")
                elif conf == "medium":
                    lab = "🟢 拉" if s.avg_IPM_delta_vs_card_mean > 0 or s.avg_CPI_delta_vs_card_mean < 0 else "🔴 拖"
                    st.caption(
                        f"{lab} 【倾向】「{s.element_value[:32]}{'…' if len(s.element_value) > 32 else ''}」 "
                        f"IPMΔ={s.avg_IPM_delta_vs_card_mean:+.1f} CPIΔ={s.avg_CPI_delta_vs_card_mean:+.2f} "
                        f"n={s.sample_size} 跨OS={cross_os}"
                    )
                else:
                    lab = "🟢 拉" if s.avg_IPM_delta_vs_card_mean > 0 or s.avg_CPI_delta_vs_card_mean < 0 else "🔴 拖"
                    ns = getattr(s, "normalized_score", 0.0)
                    st.caption(
                        f"{lab} 【稳定结论】「{s.element_value[:32]}{'…' if len(s.element_value) > 32 else ''}」 "
                        f"IPMΔ={s.avg_IPM_delta_vs_card_mean:+.1f} CPIΔ={s.avg_CPI_delta_vs_card_mean:+.2f} "
                        f"分数={ns:+.0f} n={s.sample_size} 跨OS={cross_os}"
                    )

        st.divider()
        st.markdown('<span id="sec-5"></span>', unsafe_allow_html=True)
        st.subheader("5️⃣ 下一步变体建议")
        suggestions = data.get("suggestions", [])
        if not suggestions:
            st.caption("样本不足或当前元素表现均不低于卡片均值，暂无优化建议")
        else:
            for i, s in enumerate(suggestions, 1):
                if hasattr(s, "change_layer"):
                    conf_label = {"high": "高", "medium": "中", "low": "低"}.get(getattr(s, "confidence_level", "low"), "低")
                    stype = getattr(s, "suggestion_type", "直接替换")
                    exp_metric = getattr(s, "expected_metric", "") or getattr(s, "expected_improvement", "")
                    with st.expander(f"**实验单 {i}** | {stype} | 层级:{s.change_layer} | 预期:{exp_metric} | 置信度:{conf_label}"):
                        st.write("**改动（只改一变量）**：", getattr(s, "delta_desc", "") or f"{getattr(s, 'changed_field', '')}: {s.current_value} -> {', '.join(s.candidate_alternatives[:1])}")
                        st.write("**当前取值**：", s.current_value)
                        st.write("**候选替代**：", ", ".join(s.candidate_alternatives))
                        st.write("**依据**：", s.rationale)
                else:
                    st.write(f"**建议 {i}**：{s}")


if __name__ == "__main__":
    main()
