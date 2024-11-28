@echo off
REM Creating a virtual environment (if it doesn't exist)
if not exist venv (
    python -m venv venv
)

REM Activating the virtual environment
call venv\Scripts\activate

REM Installing dependencies
if exist requirements.txt (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
) else (
    echo requirements.txt file not found. Installing basic libraries...
    pip install telethon python-dotenv colorlog rich asyncio
)

REM Deactivating the virtual environment
deactivate

echo Setup completed. Use start.bat to run the program.
pause