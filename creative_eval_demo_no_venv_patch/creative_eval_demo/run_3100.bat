@echo off
cd /d "%~dp0"
echo 正在启动决策看板 http://localhost:3100
python -m streamlit run app_demo.py --server.port 3100
pause
