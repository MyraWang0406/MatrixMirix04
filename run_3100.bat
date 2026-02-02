@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 清理占用 3100 / 8501 端口的进程...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :3100') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8501') do taskkill /F /PID %%a 2>nul

timeout /t 2 /nobreak >nul
echo.
echo 启动 Streamlit，端口 3100...
echo 浏览器访问: http://localhost:3100
echo.
streamlit run streamlit_app.py --server.port 3100
pause
