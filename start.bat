@echo off
echo Starting Mining AI Analyst...

start "Backend" wt -w 0 nt cmd /k "cd /d C:\Users\dovbg\OneDrive\Desktop\Mining\backend && python -u -m uvicorn main:app --reload --port 8000"

start "Frontend" wt -w 0 nt cmd /k "cd /d C:\Users\dovbg\OneDrive\Desktop\Mining\frontend && npm run dev"

timeout /t 3 >nul
start http://localhost:3000
