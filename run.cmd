@echo off
REM Launch Learnify. Thin wrapper around run.ps1 so PowerShell's execution policy
REM cannot block it and so the script works from cmd.exe as well.
REM
REM   run              start everything
REM   run -Fresh       start, wiping state and loading sample data
REM   run -Stop        stop everything
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
