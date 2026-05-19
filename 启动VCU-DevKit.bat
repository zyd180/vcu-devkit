@echo off
cd /d "%~dp0"

REM Try packaged executable first, fall back to Python source
if exist "dist\VCU-DevKit\VCU-DevKit.exe" (
    start "" "dist\VCU-DevKit\VCU-DevKit.exe"
) else (
    python main.py
    pause
)
