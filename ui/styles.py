"""全局样式：产品级蓝色主题、顶栏、决策结论、筛选区 Tag"""


def get_global_styles() -> str:
    return """
<style>
/* ===== 隐藏 Streamlit 工具条 ===== */
[data-testid="stToolbar"], [data-testid="stAppToolbar"],
[data-testid="stDeployButton"], [data-testid="stHeaderToolbar"],
header[data-testid="stHeader"], .stDeployButton { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }

/* ===== 留白与布局：蓝色模块铺满主内容区全宽 ===== */
.main, .main > div, .main [data-testid="stVerticalBlock"] { max-width: none !important; width: 100% !important; }
.main .block-container { padding: 1rem !important; max-width: none !important; width: 100% !important; margin: 0 !important; }
.stApp > header { padding-top: 0 !important; }
[data-testid="stVerticalBlock"] > div { gap: 0.5rem !important; }
.main .block-container > div:first-of-type [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
/* ===== 按钮不换行，铺开，右边留白 ===== */
.stButtons { flex-wrap: nowrap !important; white-space: nowrap !important; }
.stButtons button, button { white-space: nowrap !important; }
.stButton { flex-shrink: 0 !important; }

/* ===== 顶栏：统一蓝色渐变，铺满主内容区 ===== */
div:has(#ds-header-bar) { overflow: visible !important; }
div:has(#ds-header-bar) + div { margin-top: -2.4rem !important; position: relative; z-index: 10; background: transparent !important; width: 100% !important; max-width: none !important; }
div:has(#ds-header-bar) + div [data-testid="stHorizontalBlock"], div:has(#ds-header-bar) + div [data-testid="column"] { background: transparent !important; }
#ds-header-bar {
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 50%, #3B82F6 100%);
    padding: 0.6rem 1rem;
    margin: -0.5rem 0 0.6rem 0;
    border-radius: 0 0 10px 10px;
    min-height: 2.6rem;
    width: 100vw !important;
    position: relative;
    left: 50%;
    margin-left: -50vw !important;
    box-sizing: border-box;
}
/* 顶栏按钮行铺满宽度，右对齐留白 */
div:has(#ds-header-bar) + div [data-testid="stHorizontalBlock"] { width: 100% !important; justify-content: flex-start !important; }
/* 标题「决策看板」放大，左上醒目 */
#ds-header-bar + div [data-testid="stMarkdown"] span,
.ds-header-title { font-size: 1.6rem !important; font-weight: 700 !important; }
.ds-header-bar .ds-header-title { color: #fff !important; font-weight: 600; font-size: 1rem; margin-right: 0.5rem; }
.ds-header-bar .ds-tab { background: #fff; color: #2563EB; border: 1px solid #2563EB; padding: 0.35rem 0.7rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; }
.ds-header-bar .ds-tab:hover { background: #EFF6FF; }
.ds-header-bar .ds-tab.active { background: #2563EB; color: #fff !important; border-color: #2563EB; }
.ds-header-bar .ds-vertical-divider { width: 1px; height: 1.2rem; background: rgba(255,255,255,0.4); margin: 0 0.25rem; }
.ds-header-bar .ds-mode-group { display: flex; gap: 0; }
.ds-header-bar .ds-mode-btn { background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.5); padding: 0.35rem 0.6rem; font-size: 0.85rem; cursor: pointer; }
.ds-header-bar .ds-mode-btn:first-child { border-radius: 6px 0 0 6px; }
.ds-header-bar .ds-mode-btn:last-child { border-radius: 0 6px 6px 0; }
.ds-header-bar .ds-mode-btn.active { background: #fff; color: #1E3A8A !important; border-color: #fff; }

/* ===== 联系作者 ===== */
.contact-footer { position: fixed; bottom: 0; right: 0; background: #1a1a1a; color: #fff; padding: 0.35rem 0.7rem; font-size: 0.8rem; border-radius: 8px 0 0 0; z-index: 999; }
.contact-footer a { color: #fff; text-decoration: none; }

/* ===== 筛选区 multiselect tag：不截断，铺开显示 ===== */
[data-testid="stMultiSelect"] [data-baseweb="tag"],
.stMultiSelect [data-baseweb="tag"] {
  background: #E0E7FF !important; color: #2563EB !important; border-color: #93C5FD !important;
  max-width: none !important; min-width: fit-content !important; overflow: visible !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
.stMultiSelect [data-baseweb="tag"] span {
  white-space: nowrap !important; overflow: visible !important; text-overflow: clip !important; max-width: none !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"]:hover { background: #C7D2FE !important; }
[data-testid="stMultiSelect"] button[aria-label="Remove"] { color: #2563EB !important; }
[data-testid="stMultiSelect"] > div, [data-testid="stMultiSelect"] [data-baseweb="input"] { overflow: visible !important; }
/* 主 CTA（生成并评测）更大：位于筛选区 expander 内 */
.stExpander button[kind="primary"] { padding: 0.5rem 1.2rem !important; font-size: 1rem !important; font-weight: 600 !important; }

/* ===== 决策结论 Summary：6px 粗蓝条、白底、圆角 ===== */
.decision-summary-hero {
    padding: 1rem 1.2rem;
    margin: 1rem 0;
    border-radius: 8px;
    border-left: 6px solid #2563EB;
    background: #fff !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.decision-summary-hero.status-pass { border-left-color: #2563EB; background: #F0F9FF !important; }
.decision-summary-hero.status-fail { border-left-color: #DC2626; background: #FEF2F2 !important; }
.decision-summary-hero.status-warn { border-left-color: #2563EB; background: #FFFBEB !important; }
.summary-label { font-weight: 600; margin-bottom: 0.4rem; font-size: 0.9rem; color: #1E3A8A; }
.summary-status { font-size: 1.1rem; font-weight: 600; margin: 0.5rem 0; color: #1E293B; }
.summary-row { margin: 0.25rem 0; font-size: 0.9rem; color: #475569; }
.decision-summary-hero .ds-summary-btns button { background: #f1f5f9 !important; color: #475569 !important; border: 1px solid #e2e8f0 !important; }
.decision-summary-hero .ds-summary-btns button:hover { background: #e2e8f0 !important; }

/* ===== 主按钮 ===== */
button[kind="primary"] { background-color: #2563EB !important; color: #fff !important; border: none !important; }
button[kind="secondary"] { background: #f1f5f9 !important; color: #475569 !important; border: 1px solid #e2e8f0 !important; }

/* ===== 电梯导航 ===== */
.elevator-title { font-weight: 600; font-size: 0.9rem; color: #1E3A8A; }
.elevator-link { display: block; padding: 0.3rem 0.5rem; font-size: 0.85rem; color: #475569; text-decoration: none; border-radius: 6px; }
.elevator-link:hover { background: #EFF6FF; color: #2563EB; }

/* ===== 表格 ===== */
[data-testid="stDataFrame"], .stDataFrame { overflow-x: auto !important; max-width: 100%; }
[data-testid="stMetric"] { font-size: 1rem !important; }
[data-testid="stMetric"] label { font-size: 0.85rem !important; }

@media (max-width: 768px) {
    .main .block-container { padding: 0.5rem !important; max-width: 100% !important; }
    .ds-header-bar { flex-wrap: wrap !important; }
}
</style>
"""
