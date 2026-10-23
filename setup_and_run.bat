@echo off
REM Creates a virtual environment, installs packages, runs tests, starts the web app.
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    py -3 -m venv venv
    if errorlevel 1 python -m venv venv
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Package installation failed. Check your internet connection and Python installation.
    pause
    exit /b 1
)

echo.
echo Running tests...
python test_market_analysis.py
if errorlevel 1 (
    echo Tests failed. See the error above.
    pause
    exit /b 1
)

echo.
echo Starting the app at http://127.0.0.1:8000  (press Ctrl+C to stop)
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8000"
python main.py
pause
