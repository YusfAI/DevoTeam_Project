@echo off
setlocal
title DevoTeam Dashboard - Lanceur

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

echo ============================================
echo   DevoTeam Dashboard - Demarrage
echo ============================================
echo.

REM --- 1. Backend FastAPI (http://127.0.0.1:8000) ---
echo [Backend] demarrage...
start "DevoTeam Backend" cmd /k "cd /d ""%PROJECT_ROOT%"" && python -m uvicorn backend.main:app --reload"

REM --- 2. Dashboards Bruin DAC (http://localhost:8321), affiches en iframe par l'UI ---
echo [DAC] demarrage...
start "DevoTeam DAC" cmd /k "cd /d ""%PROJECT_ROOT%\dac"" && ""%USERPROFILE%\.local\bin\dac.exe"" serve --dir . --port 8321"

REM --- 3. Frontend Vite (http://localhost:5173) ---
echo [Frontend] demarrage...
start "DevoTeam Frontend" cmd /k "cd /d ""%PROJECT_ROOT%\frontend"" && npm run dev"

REM --- 4. Ouvrir la page dans le navigateur une fois Vite pret ---
echo.
echo Ouverture du navigateur dans quelques secondes...
timeout /t 6 /nobreak >NUL
start "" "http://localhost:5173"

echo.
echo Tout est lance. Les serveurs tournent dans leurs propres fenetres
echo (ne pas les fermer). Cette fenetre peut etre fermee.
echo.
pause
endlocal
