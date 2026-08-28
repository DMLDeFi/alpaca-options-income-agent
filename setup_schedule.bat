@echo off
set RUNNER=C:\Users\hp\OneDrive\Desktop\AlpacaHackathon\run_agent.bat

schtasks /Create /TN "AlpacaAgent_1435" /TR "\"%RUNNER%\"" /SC DAILY /ST 14:35 /F
schtasks /Create /TN "AlpacaAgent_1730" /TR "\"%RUNNER%\"" /SC DAILY /ST 17:30 /F
schtasks /Create /TN "AlpacaAgent_2045" /TR "\"%RUNNER%\"" /SC DAILY /ST 20:45 /F

echo.
echo Done. Three scheduled tasks created: AlpacaAgent_1435, AlpacaAgent_1730, AlpacaAgent_2045
pause
