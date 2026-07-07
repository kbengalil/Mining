@echo off
echo Starting Mining AI Analyst...

start "Backend" cmd /k "cd /d C:\Users\dovbg\OneDrive\Desktop\Mining\backend && python -m uvicorn main:app --reload --port 8000"

start "Frontend" cmd /k "cd /d C:\Users\dovbg\OneDrive\Desktop\Mining\frontend && npm run dev"

timeout /t 3 >nul
start http://localhost:3000
