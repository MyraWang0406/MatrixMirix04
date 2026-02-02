"""统一 samples 路径：始终使用仓库根目录 /samples。Streamlit Cloud 部署时 repo 根目录即工作目录。"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = REPO_ROOT / "samples"
