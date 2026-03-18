@echo off
chcp 65001 >nul
title 图片压缩工具
cd /d "%~dp0"

:: 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo 未检测到 Python 环境，准备自动下载并安装...
        echo 正在下载 Python 3.11 安装包，请稍候...
        curl -o python-installer.exe https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe
        if exist python-installer.exe (
            echo 下载完成！正在静默安装 Python...
            echo 若弹出管理员权限提示，请点击“是”允许安装！
            start /wait python-installer.exe InstallAllUsers=1 PrependPath=1 Include_test=0 target_dir="C:\Python311"
            echo 安装过程结束，正在清理安装包...
            del python-installer.exe
            
            :: 尝试刷新环境变量并再次检测
            set PATH=%PATH%;C:\Python311;C:\Python311\Scripts
            python --version >nul 2>&1
            if %errorlevel% neq 0 (
                 echo Python 应该已安装成功，但环境变量未能立即生效，请重新运行此脚本。如果仍不行，请重启电脑。
                 pause
                 exit /b 1
            )
        ) else (
            echo Python 下载失败，请手动前往 https://www.python.org/ 下载安装，请务必勾选 "Add Python to PATH"！
            pause
            exit /b 1
        )
    )
)

:: 检查并安装依赖
pip show customtkinter >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在检查并安装必要依赖，请稍等...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        py -m pip install -r requirements.txt
    )
)

:: 启动主程序
echo 正在启动图片压缩工具...
python main.py
if %errorlevel% neq 0 (
    py main.py
)
pause
