"""
诊断模块：可解释诊断 + 可行动处方。
基于 explore/validate 指标、门禁状态、样本量、OS 结果，
输出 failure_type、primary_signal、recommended_actions。

✅升级点（你要的）：
- 增加 diagnosis_title / diagnosis_explanation / action_hint：让 UI 不再只显示黑话
- 增加 decision_state：统一输出“现在到底该干啥”的决策状态（闭环关键）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -------- 枚举（与 spec 对齐）--------

FAILURE_TYPE = (
    "INCONCLUSIVE",      # 样本不足，不下结论
    "EFFICIENCY_FAIL",   # Explore 效率不行（IPM 低 / CPI 高）
    "QUALITY_FAIL",      # Validate 质量不行（early_roas 低）
    "HANDOFF_MISMATCH",  # 承接断裂（IPM 还行但 CPI/ROAS 崩）
    "OS_DIVERGENCE",     # iOS/Android 结论不一致
    "MIXED_SIGNALS",     # 指标打架 / 难归因
)

PRIMARY_SIGNAL = (
    "SAMPLE_TOO_LOW",
    "IPM_DROP",
    "CPI_SPIKE",
    "ROAS_DROP",
    "IPM_OK_BUT_CPI_BAD",
    "IPM_OK_BUT_ROAS_BAD",
    "IOS_PASS_ANDROID_FAIL",
    "ANDROID_PASS_IOS_FAIL",
)

# 决策状态（给 Summary 第一屏用，避免“样本不足/不确定”废话）
DECISION_STATE = (
    "INSUFFICIENT_DATA",  # 样本不足：继续跑，不改结构
    "FIX_HANDOFF",        # 承接问题：先补证据/承接一致性
    "OS_TUNE",            # 双端分歧：端内修正（只动一端）
    "CHANGE_STRUCTURE",   # 结构效率问题：改 hook/why_now/cta
    "CHANGE_QUALITY",     # 质量问题：改 why_you/why_now/cta
    "READY_TO_SCALE",     # 可以放量
    "REVIEW",             # 需要人工复核
)

MIN_SAMPLES = 6
MIN_WINDOWS = 3


@dataclass
class PrescriptionAction:
    """单条处方动作"""

    action: str = ""        # RESAMPLE / CHANGE_HOOK / CHANGE_WHY_NOW / CHANGE_CTA / CHANGE_WHY_YOU / ADD_EVIDENCE / FIX_HANDOFF / SCALE_UP
    change_field: str = ""  # hook_type / why_you_bucket / why_now_trigger / cta / 空
    direction: str = ""     # 方向文案
    experiment_recipe: str = ""  # OFAAT 说明
    target_os: str = ""     # iOS / Android / 空（端内修正时用）
    reason: str = ""        # 触发原因


@dataclass
class DiagnosisResult:
    """诊断输出：failure_type, primary_signal, recommended_actions"""

    failure_type: str = "INCONCLUSIVE"
    primary_signal: str = "SAMPLE_TOO_LOW"
    recommended_actions: list[PrescriptionAction] = field(default_factory=list)
    detail: str = ""

    # ✅新增：让 UI/Prompt 可解释、可行动
    decision_state: str = "INSUFFICIENT_DATA"
    diagnosis_title: str = "样本不足（不下结论）"
    diagnosis_explanation: list[str] = field(default_factory=list)
    action_hint: str = ""


def _compute_decision_state(d: DiagnosisResult) -> str:
    if not d.failure_type:
        return "READY_TO_SCALE"
    if d.failure_type == "INCONCLUSIVE":
        return "INSUFFICIENT_DATA"
    if d.failure_type == "OS_DIVERGENCE":
        return "OS_TUNE"
    if d.failure_type == "HANDOFF_MISMATCH":
        return "FIX_HANDOFF"
    if d.failure_type == "EFFICIENCY_FAIL":
        return "CHANGE_STRUCTURE"
    if d.failure_type == "QUALITY_FAIL":
        return "CHANGE_QUALITY"
    if d.failure_type == "MIXED_SIGNALS":
        return "REVIEW"
    return "REVIEW"


def _enrich_diagnosis_text(d: DiagnosisResult) -> DiagnosisResult:
    """
    把 failure_type/primary_signal 翻译成：
    - diagnosis_title（人话标题）
    - diagnosis_explanation（原因要点）
    - action_hint（优先动作提示）
    """
    title_map = {
        "INCONCLUSIVE": "样本不足（不下结论）",
        "EFFICIENCY_FAIL": "效率不过线（结构先别判死刑）",
        "QUALITY_FAIL": "质量不过线（转化质量不足）",
        "HANDOFF_MISMATCH": "承接断裂（骗点击/预期落差）",
        "OS_DIVERGENCE": "双端分歧（端内修正）",
        "MIXED_SIGNALS": "信号混杂（需要收敛变量）",
        "": "结构成立（可放量）",
    }
    hint_map = {
        "INCONCLUSIVE": "补到门槛再判断：n≥6 或 窗口≥3。样本不足≠FAIL，先别换结构。",
        "EFFICIENCY_FAIL": "优先改 Hook（更强反差/结果先行），保持其余字段不动（OFAAT）。",
        "QUALITY_FAIL": "优先改 why_you（价值/证据/人群匹配），其次 why_now/CTA（避免强诱导）。",
        "HANDOFF_MISMATCH": "先补证据与承接一致性（到手价/对比/口碑/售后等），不要先换 Hook。",
        "OS_DIVERGENCE": "只修一端：保留通过端不动，失败端替换表达/节奏或 Hook（OFAAT）。",
        "MIXED_SIGNALS": "先收敛动机/人群或 why_you，再讨论 Hook；否则越改越乱。",
        "": "跨窗稳定 + OS 一致 + 指标达线：可以小步放量。",
    }

    expl = []
    ps = (d.primary_signal or "").upper()

    if d.failure_type == "INCONCLUSIVE":
        expl.append("样本/窗口未达门槛：此时任何“结构不行”的结论都不可靠")
    if ps == "IPM_DROP":
        expl.append("IPM 信号异常：转化效率不足（前三秒抓不住/信息不清）")
    if ps == "CPI_SPIKE":
        expl.append("CPI 信号异常：成本上升（点击质量或承接成本更高）")
    if ps == "ROAS_DROP":
        expl.append("early_ROAS 信号异常：质量不足（用户预期落差/产品价值证据不够）")
    if ps in ("IPM_OK_BUT_CPI_BAD", "IPM_OK_BUT_ROAS_BAD"):
        expl.append("IPM 尚可但 CPI/ROAS 崩：典型承接断裂（噱头/强刺激/证据不足）")
    if ps in ("IOS_PASS_ANDROID_FAIL", "ANDROID_PASS_IOS_FAIL"):
        expl.append("iOS/Android Explore 结论不一致：优先端内修正，别全局推翻结构")

    if not expl:
        # 兜底：避免 explanation 空
        if d.failure_type:
            expl = [f"诊断类型：{d.failure_type}（可参考处方动作执行）"]
        else:
            expl = ["结构成立：稳定性与一致性达线"]

    d.diagnosis_title = title_map.get(d.failure_type, f"诊断：{d.failure_type}")
    d.diagnosis_explanation = expl
    d.action_hint = hint_map.get(d.failure_type, "")
    d.decision_state = _compute_decision_state(d)
    return d


def diagnose(
    *,
    explore_ios: Any = None,
    explore_android: Any = None,
    validate_result: Any = None,
    metrics: list[Any] | None = None,
    windowed_metrics: list[Any] | None = None,
) -> DiagnosisResult:
    """
    诊断：严格按优先级顺序执行。
    Step 0: 样本门槛 → INCONCLUSIVE
    Step 1: OS 分歧 → OS_DIVERGENCE
    Step 2: 效率 vs 质量 → EFFICIENCY_FAIL / QUALITY_FAIL
    Step 3: 承接断裂 → HANDOFF_MISMATCH
    Step 4: 混合信号 → MIXED_SIGNALS
    """
    metrics = metrics or []
    n_samples = len([m for m in metrics if not getattr(m, "baseline", False)])
    detail_rows = getattr(validate_result, "detail_rows", None) or []
    n_windows = len(detail_rows)

    exp_ios_pass = (
        getattr(explore_ios, "gate_status", "") == "PASS" if explore_ios else False
    )
    exp_android_pass = (
        getattr(explore_android, "gate_status", "") == "PASS" if explore_android else False
    )
    val_pass = (
        getattr(validate_result, "validate_status", "") == "PASS" if validate_result else False
    )
    sm = getattr(validate_result, "stability_metrics", None)
    risk_notes = list(getattr(validate_result, "risk_notes", None) or [])

    # ----- Step 0: 样本门槛 -----
    if n_samples < MIN_SAMPLES or n_windows < MIN_WINDOWS:
        d = DiagnosisResult(
            failure_type="INCONCLUSIVE",
            primary_signal="SAMPLE_TOO_LOW",
            recommended_actions=[
                PrescriptionAction(
                    action="RESAMPLE",
                    change_field="",
                    direction="保持原结构不变",
                    experiment_recipe="同结构复测，优先补足样本门槛（n≥6 或窗口≥3）",
                    reason=f"样本 n={n_samples} 或窗口={n_windows} 不足",
                ),
            ],
            detail=f"样本 n={n_samples} 或窗口={n_windows} 不足，无法下结论。样本不足≠FAIL，禁止输出「结构不行」。",
        )
        return _enrich_diagnosis_text(d)

    # ----- Step 1: OS 分歧 -----
    if exp_ios_pass != exp_android_pass:
        if exp_ios_pass and not exp_android_pass:
            primary = "IOS_PASS_ANDROID_FAIL"
            target_os = "Android"
            direction = "Android 端替换表达/节奏或 hook（保持其它字段不动）"
        else:
            primary = "ANDROID_PASS_IOS_FAIL"
            target_os = "iOS"
            direction = "iOS 端替换表达/节奏或 hook（保持其它字段不动）"
        d = DiagnosisResult(
            failure_type="OS_DIVERGENCE",
            primary_signal=primary,
            recommended_actions=[
                PrescriptionAction(
                    action="FIX_HANDOFF",
                    change_field="hook_type",
                    direction=direction,
                    experiment_recipe=f"端内修正：保留通过端不动，失败端仅替换 hook_type 候选池（OFAAT）",
                    target_os=target_os,
                    reason="同一变体 iOS 与 Android Explore 结论不一致",
                ),
            ],
            detail=f"{target_os} Explore 未过，双端结果不一致",
        )
        return _enrich_diagnosis_text(d)

    # ----- Step 2: 效率 vs 质量 -----
    # Explore FAIL 且（IPM 低 或 CPI 高）→ EFFICIENCY_FAIL
    if (not exp_ios_pass) and (not exp_android_pass):
        primary = "IPM_DROP"
        if any("CPI" in n for n in risk_notes) and not any("IPM" in n and "回撤" in n for n in risk_notes):
            primary = "CPI_SPIKE"
        actions = [
            PrescriptionAction(
                action="CHANGE_HOOK",
                change_field="hook_type",
                direction="更直接爽点/结果先行/反差更强（前三秒抓住动机）",
                experiment_recipe="OFAAT：仅改 hook_type，固定其余字段，生成 N 个变体",
                reason="Explore FAIL，IPM/CPI 效率未达 baseline",
            ),
            PrescriptionAction(
                action="CHANGE_WHY_NOW",
                change_field="why_now_trigger",
                direction="更强「现在必须」触发，但注意不要强刺激骗点击",
                experiment_recipe="OFAAT：仅改 why_now_trigger",
                reason="Explore FAIL，可尝试强化 why now",
            ),
            PrescriptionAction(
                action="CHANGE_CTA",
                change_field="cta",
                direction="最后才动 CTA：更具体、更低阻力",
                experiment_recipe="OFAAT：仅改 CTA",
                reason="Explore FAIL，最后再动 CTA",
            ),
        ]
        d = DiagnosisResult(
            failure_type="EFFICIENCY_FAIL",
            primary_signal=primary,
            recommended_actions=actions,
            detail="Explore FAIL，IPM 低或 CPI 高，效率未达 baseline",
        )
        return _enrich_diagnosis_text(d)

    # Validate FAIL 且 early_roas 低 → QUALITY_FAIL 或 HANDOFF_MISMATCH
    if exp_ios_pass and exp_android_pass and (not val_pass):
        early_roas_low = any("ROAS" in n or "转化" in n or "early" in n.lower() for n in risk_notes)
        ipm_ok_cpi_bad = any("CPI" in n for n in risk_notes) and not any("IPM" in n and "回撤" in n for n in risk_notes)
        ipm_ok_roas_bad = early_roas_low

        # ----- Step 3: 承接断裂 -----
        if ipm_ok_cpi_bad or ipm_ok_roas_bad:
            primary = "IPM_OK_BUT_CPI_BAD" if ipm_ok_cpi_bad else "IPM_OK_BUT_ROAS_BAD"
            actions = [
                PrescriptionAction(
                    action="ADD_EVIDENCE",
                    change_field="",
                    direction="补证据/承接一致性（到手价/对比/口碑/售后/发货时效其一）",
                    experiment_recipe="延长观察窗口 + 补足证据展示，先把承诺兑现",
                    reason="IPM 不差但 CPI/ROAS 崩，承接断裂",
                ),
                PrescriptionAction(
                    action="CHANGE_WHY_NOW",
                    change_field="why_now_trigger",
                    direction="减少强诱导（避免骗点击），提高承接一致性",
                    experiment_recipe="OFAAT：仅改 why_now_trigger（更保守）",
                    reason="承接断裂时不优先动 hook",
                ),
                PrescriptionAction(
                    action="CHANGE_CTA",
                    change_field="cta",
                    direction="避免过强诱导：更像“下一步操作”而不是“强刺激下单”",
                    experiment_recipe="OFAAT：仅改 CTA",
                    reason="CTA 可能过强诱导",
                ),
            ]
            d = DiagnosisResult(
                failure_type="HANDOFF_MISMATCH",
                primary_signal=primary,
                recommended_actions=actions,
                detail="Explore 过但 Validate 未过，IPM 还行但 CPI/ROAS 崩，承接断裂",
            )
            return _enrich_diagnosis_text(d)

        # Validate FAIL 且 early_roas 低（非典型承接断裂路径）
        if early_roas_low:
            actions = [
                PrescriptionAction(
                    action="CHANGE_WHY_YOU",
                    change_field="why_you_bucket",
                    direction="强化价值/证据/人群匹配（别只讲“便宜”，要讲“为什么你值得”）",
                    experiment_recipe="OFAAT：仅改 why_you_bucket",
                    reason="Validate FAIL，early_roas 低，质量不行",
                ),
                PrescriptionAction(
                    action="CHANGE_WHY_NOW",
                    change_field="why_now_trigger",
                    direction="减少强刺激，提升一致性",
                    experiment_recipe="OFAAT：仅改 why_now_trigger",
                    reason="减少强诱导，提升一致性",
                ),
                PrescriptionAction(
                    action="CHANGE_CTA",
                    change_field="cta",
                    direction="避免过强诱导",
                    experiment_recipe="OFAAT：仅改 CTA",
                    reason="CTA 避免过强诱导",
                ),
            ]
            d = DiagnosisResult(
                failure_type="QUALITY_FAIL",
                primary_signal="ROAS_DROP",
                recommended_actions=actions,
                detail="Validate FAIL，early_roas 低，转化质量不行",
            )
            return _enrich_diagnosis_text(d)

        # Validate FAIL 但非明确 ROAS/CPI 主导 → 可能是稳定性不足
        ipm_drop = getattr(sm, "ipm_drop_pct", 0) or 0 if sm else 0
        cpi_inc = getattr(sm, "cpi_increase_pct", 0) or 0 if sm else 0
        if ipm_drop > 20:
            primary = "IPM_DROP"
        elif cpi_inc > 15:
            primary = "CPI_SPIKE"
        else:
            primary = "ROAS_DROP"
        actions = [
            PrescriptionAction(
                action="ADD_EVIDENCE",
                change_field="",
                direction="延长观察补足稳定性证据（跨窗一致后再下结论）",
                experiment_recipe="同结构复测，补足窗口证据",
                reason="Validate FAIL，波动或回撤超阈值",
            ),
        ]
        d = DiagnosisResult(
            failure_type="HANDOFF_MISMATCH",
            primary_signal=primary,
            recommended_actions=actions,
            detail="Explore 过但 Validate 未过，跨窗承接或稳定性不足",
        )
        return _enrich_diagnosis_text(d)

    # ----- Step 4: 全部通过 → 放量 -----
    if exp_ios_pass and exp_android_pass and val_pass:
        ipm_cv = getattr(sm, "ipm_cv", 0) if sm else 0
        if ipm_cv < 0.05:
            d = DiagnosisResult(
                failure_type="",
                primary_signal="",
                recommended_actions=[
                    PrescriptionAction(
                        action="SCALE_UP",
                        change_field="",
                        direction="放量",
                        experiment_recipe="跨窗稳定、OS 一致、指标达线",
                        reason="结构成立",
                    ),
                ],
                detail="跨窗稳定、OS 一致、指标达线，结构成立",
            )
            return _enrich_diagnosis_text(d)

        # 门禁过但波动大 → 仍然当承接/稳定性风险处理
        d = DiagnosisResult(
            failure_type="HANDOFF_MISMATCH",
            primary_signal="IPM_DROP",
            recommended_actions=[
                PrescriptionAction(
                    action="ADD_EVIDENCE",
                    change_field="",
                    direction="延长观察补足稳定性",
                    experiment_recipe="同结构复测，补足窗口证据",
                    reason="门禁通过但 IPM 波动大",
                ),
            ],
            detail="门禁通过但 IPM 波动大，建议延长观察",
        )
        return _enrich_diagnosis_text(d)

    # ----- Step 5: 混合信号 -----
    d = DiagnosisResult(
        failure_type="MIXED_SIGNALS",
        primary_signal="",
        recommended_actions=[
            PrescriptionAction(
                action="CHANGE_WHY_YOU",
                change_field="why_you_bucket",
                direction="动机/人群错配：先收敛 why_you 或 segment",
                experiment_recipe="OFAAT：仅改 why_you_bucket",
                reason="指标打架，难归因",
            ),
        ],
        detail="指标互相打架，建议走动机/人群错配路线",
    )
    return _enrich_diagnosis_text(d)


def diagnosis_to_next_action(diag: DiagnosisResult) -> str:
    """将 diagnosis 映射为 Summary 显示的 next_action 文案（更像动作而不是黑话）"""
    if not diag.failure_type:
        return "放量"
    if diag.failure_type == "INCONCLUSIVE":
        return "补样本（不改结构）"
    if diag.failure_type == "OS_DIVERGENCE":
        return "端内修正（只改一端）"
    if diag.failure_type == "EFFICIENCY_FAIL":
        return "换 Hook（OFAAT）"
    if diag.failure_type == "QUALITY_FAIL":
        return "换 why_you（OFAAT）"
    if diag.failure_type == "HANDOFF_MISMATCH":
        return "补证据/修承接"
    if diag.failure_type == "MIXED_SIGNALS":
        return "收敛人群/why_you"
    return "复核"
