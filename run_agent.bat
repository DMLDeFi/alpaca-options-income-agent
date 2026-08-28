@echo off
cd /d "C:\Users\hp\OneDrive\Desktop\AlpacaHackathon"
echo ---- %DATE% %TIME% ---- >> logs\scheduled_run.log
"C:\Users\hp\OneDrive\Desktop\AlpacaHackathon\.venv\Scripts\python.exe" src\run_agent.py >> logs\scheduled_run.log 2>&1

git add public\status.json >> logs\scheduled_run.log 2>&1
git commit -m "Update status: %DATE% %TIME%" >> logs\scheduled_run.log 2>&1
git push >> logs\scheduled_run.log 2>&1
