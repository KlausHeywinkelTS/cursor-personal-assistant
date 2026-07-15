@echo off

REM Cursor via WMI starten - komplett unabhaengig
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "([wmiclass]'Win32_Process').Create('\"C:\Program Files\cursor\Cursor.exe\" \"C:\Users\Kl6713\AI-Agent\cursor-personal-assistant\"')" > nul
