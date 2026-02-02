"""
在 3100 端口启动决策看板
用法：python run_demo_3100.py
"""
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
APP = DIR / "app_demo.py"

def main():
    if not APP.exists():
        print(f"错误：找不到 {APP}")
        sys.exit(1)
    cmd = [sys.executable, "-m", "streamlit", "run", str(APP), "--server.port", "3100"]
    print(f"启动中: http://localhost:3100")
    print("按 Ctrl+C 停止")
    subprocess.run(cmd, cwd=str(DIR))

if __name__ == "__main__":
    main()
