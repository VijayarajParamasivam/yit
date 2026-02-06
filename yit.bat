@echo off
set "YIT_DIR=%~dp0"

if exist "%YIT_DIR%venv\Scripts\python.exe" (
    "%YIT_DIR%venv\Scripts\python.exe" "%YIT_DIR%yit.py" %*
    exit /b %errorlevel%
)

echo [ERROR] Yit is not installed correctly.
echo.
echo What would you like to do?
echo [Y] Run Installer Now [Fix automatically]
echo [O] Open Folder [Fix manually]
echo [N] Exit
echo.

choice /C YON /M "Select an option"
if errorlevel 3 exit /b 1
if errorlevel 2 start "" "%YIT_DIR%" & exit /b 1
if errorlevel 1 call "%YIT_DIR%setup_installer.bat"
