# streamlit_app.py - 仓库根目录入口（最终要跑 app_demo.main）

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st

# --- 1) 路径：唯一模块源（与 app_demo.py 一致） ---
ROOT = Path(__file__).resolve().parent
_PKG = ROOT / "MatrixMirix02"
_PKG_PATH = str(_PKG.resolve()) if _PKG.exists() else str(ROOT.resolve())
if _PKG_PATH not in sys.path:
    sys.path.insert(0, _PKG_PATH)

st.set_page_config(
    page_title="投放实验决策系统 (Decision Support System)",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    import app_demo
    app_demo.main()

except Exception as e:
    # Streamlit 的 StopException 不要吞
    if type(e).__name__ == "StopException":
        raise

    st.error(f"运行失败：{e}")
    with st.expander("错误详情"):
        st.code(traceback.format_exc(), language="text")