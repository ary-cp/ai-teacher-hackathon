@echo off
cd /d "%~dp0backend"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env ( copy .env.example .env && echo. && echo === Add your GROQ_API_KEY to backend\.env, then re-run === && pause )
uvicorn main:app --reload --port 8000
