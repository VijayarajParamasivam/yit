@echo off
echo Launching Yit Installer...
PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0install_yit.ps1'"
pause
