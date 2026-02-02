"""
30 秒决策结论：综合 iOS/Android Explore + Validate 状态。
无 Streamlit 依赖，可单独测试。
使用 diagnosis 模块输出 next_action，替代泛泛的「复测」。

【门禁 ≠ 结论】
- 样本不足 → 不下结论（仅提示补足数据）
- 门禁失败 → 结构暂不成立（需复测或换层）
- 仅当：跨窗稳定 + OS 不冲突 + 指标达线 → 才允许「结构成立」
"""

from __future__ import annotations

from diagnosis import diagnose, diagnosis_to_next_action

MIN_SAMPLES = 6
MIN_WINDOWS = 3
IPM_CV_THRESHOLD_FOR_SCALE = 0.05
DEFAULT_SCALE_UP_STEP = "20%"


def compute_decision_summary(results: dict) -> dict:
    """
    30 秒决策结论：综合 iOS/Android Explore + Validate 状态。
    返回: status(red/yellow/green), status_text, reason, risk, next_step, insufficient, diagnosis
    """
    explore_ios = results.get("explore_ios")
    explore_android = results.get("explore_android")
    validate_result = results.get("validate_result")
    metrics = results.get("metrics", [])
    scale_up_step = DEFAULT_SCALE_UP_STEP

    n_samples = len([m for m in metrics if not m.baseline])
    detail_rows = getattr(validate_result, "detail_rows", None) or []
    n_windows = len(detail_rows)
    insufficient = n_samples < MIN_SAMPLES or n_windows < MIN_WINDOWS

    exp_ios_pass = explore_ios.gate_status == "PASS" if explore_ios else False
    exp_android_pass = explore_android.gate_status == "PASS" if explore_android else False
    val_pass = validate_result.validate_status == "PASS" if validate_result else False
    sm = getattr(validate_result, "stability_metrics", None)
    ipm_cv = getattr(sm, "ipm_cv", 1.0) if sm else 1.0

    # 原因
    reason_parts = []
    reason_parts.append("iOS Explore PASS" if exp_ios_pass else "iOS Explore FAIL")
    reason_parts.append("Android Explore PASS" if exp_android_pass else "Android Explore FAIL")
    reason_parts.append("Validate PASS" if val_pass else "Validate FAIL")
    if insufficient:
        reason_parts.append("样本不足（n<6 或窗口<3）")
    reason_str = "；".join(reason_parts)

    # 风险
    risk_parts = list(getattr(validate_result, "risk_notes", None) or [])[:2]
    baseline_list = [m for m in metrics if m.baseline]
    variant_list = [m for m in metrics if not m.baseline]
    if baseline_list and variant_list:
        bl_cpi = sum(m.cpi for m in baseline_list) / len(baseline_list)
        var_cpi = sum(m.cpi for m in variant_list) / len(variant_list)
        if bl_cpi > 0:
            cpi_delta = (var_cpi - bl_cpi) / bl_cpi
            if cpi_delta > 0.05:
                risk_parts.append(f"CPI +{cpi_delta:.1%} 高于 baseline")
    risk_str = "；".join(risk_parts) if risk_parts else "暂无显著风险"

    # 诊断：failure_type, primary_signal, recommended_actions + 人话字段
    diag = diagnose(
        explore_ios=explore_ios,
        explore_android=explore_android,
        validate_result=validate_result,
        metrics=metrics,
    )
    next_action = diagnosis_to_next_action(diag)

    # 状态与下一步（使用 diagnosis 处方）
    # ✅额外：把 decision_state 放到 status_text 的语义里（让第一屏更像“决策系统”）
    if diag.decision_state == "READY_TO_SCALE" and val_pass and ipm_cv < IPM_CV_THRESHOLD_FOR_SCALE:
        status = "green"
        status_text = f"🟢 建议放量({scale_up_step})"
        next_step = "放量"
    elif diag.decision_state == "INSUFFICIENT_DATA":
        status = "yellow"
        status_text = f"🟡 样本不足：继续跑({scale_up_step})"
        next_step = next_action
        reason_str += f"（{diag.detail}）"
    elif diag.decision_state in ("FIX_HANDOFF", "OS_TUNE", "CHANGE_STRUCTURE", "CHANGE_QUALITY", "REVIEW"):
        # 只要不是 READY_TO_SCALE / INSUFFICIENT_DATA，默认都不建议放量（红/黄由 val_pass 决定）
        if not val_pass:
            status = "red"
            status_text = "🔴 不建议放量"
        else:
            status = "yellow"
            status_text = f"🟡 小步复测({scale_up_step})"
        next_step = next_action
    else:
        status = "yellow"
        status_text = f"🟡 小步复测({scale_up_step})"
        next_step = next_action

    # 将 recommended_actions 转为可序列化
    actions_ser = [
        {
            "action": a.action,
            "change_field": a.change_field,
            "direction": a.direction,
            "experiment_recipe": a.experiment_recipe,
            "target_os": a.target_os,
            "reason": a.reason,
        }
        for a in diag.recommended_actions
    ]

    return {
        "status": status,
        "status_text": status_text,
        "reason": reason_str,
        "risk": risk_str,
        "next_step": next_step,
        "insufficient": insufficient,
        "diagnosis": {
            "failure_type": diag.failure_type,
            "primary_signal": diag.primary_signal,
            "decision_state": diag.decision_state,
            "diagnosis_title": diag.diagnosis_title,
            "diagnosis_explanation": list(diag.diagnosis_explanation or []),
            "action_hint": diag.action_hint,
            "recommended_actions": actions_ser,
            "detail": diag.detail,
        },
    }
