@echo off
REM Runs the analysis from the command line. Extra options are passed through, e.g.:
REM   run_cli.bat --refresh
REM   run_cli.bat --cache-stats
cd /d "%~dp0"
if not exist venv (
    echo Virtual environment not found. Run setup_and_run.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python run_market_analysis.py %*
pause
