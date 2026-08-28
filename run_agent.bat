@echo off
cd /d "C:\Users\hp\OneDrive\Desktop\AlpacaHackathon"
echo ---- %DATE% %TIME% ---- >> logs\scheduled_run.log
"C:\Users\hp\OneDrive\Desktop\AlpacaHackathon\.venv\Scripts\python.exe" src\run_agent.py >> logs\scheduled_run.log 2>&1
