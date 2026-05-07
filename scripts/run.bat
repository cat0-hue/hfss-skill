@echo off
chcp 65001 >nul
echo ============================================
echo   天线仿真 - PyAEDT + ANSYS AEDT
echo ============================================
echo.

cd /d "%~dp0.."

set PYTHON311=C:\Users\Gin\AppData\Local\Programs\Python\Python311\python.exe

if not exist "%PYTHON311%" (
    echo [错误] 未找到 Python 3.11: %PYTHON311%
    pause
    exit /b 1
)

echo 运行仿真...
"%PYTHON311%" scripts\sim_core.py

echo.
echo 仿真脚本执行完毕！
pause
