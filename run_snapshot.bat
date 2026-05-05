@echo off
REM Pipedrive Month-End Snapshot Runner
REM Generates CSVs only — no email
REM Use this to test before wiring up full automation

echo ========================================
echo Pipedrive Pipeline Snapshot
echo ========================================
echo.

cd /d %~dp0

python pipeline_snapshot.py

echo.
echo Press any key to close...
pause > nul
