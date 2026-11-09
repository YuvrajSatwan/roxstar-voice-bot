@echo off
echo Starting STS Lab Backend Supervisor...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_sts.py
) else if exist "..\roxstar-ai-voice-assistant\.venv\Scripts\python.exe" (
    "..\roxstar-ai-voice-assistant\.venv\Scripts\python.exe" run_sts.py
) else (
    python run_sts.py
)
pause

