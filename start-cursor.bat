@echo off

REM VS Code via WMI starten - komplett unabhaengig
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "([wmiclass]'Win32_Process').Create('\"C:\Program Files\Microsoft VS Code\Code.exe\" \"C:\Users\Kl6713\AI-Agent\cursor-personal-assistant\"')" > nul
