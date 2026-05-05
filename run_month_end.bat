@echo off
REM Month-End Pipeline Snapshot + Email Automation
REM Runs on last day of each month via Task Scheduler

echo ========================================
echo Pipeline Snapshot + Email Automation
echo ========================================
echo.

cd /d %~dp0

echo Step 1: Generating pipeline snapshot...
echo.
python pipeline_snapshot.py

echo.
echo Step 2: Sending email...
echo.
python email_snapshot.py

echo.
echo ========================================
echo Complete!
echo ========================================
echo.
