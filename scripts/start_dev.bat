@echo off
setlocal
title DevoTeam Dashboard - Lanceur

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

REM Les binaires Bruin sont installes dans %USERPROFILE%\.local\bin, que l'installeur
REM n'ajoute PAS au PATH systeme. C'est indispensable ici : dac.exe delegue l'execution
REM du SQL a "bruin", qu'il cherche dans le PATH — sans cette ligne, les widgets
REM affichent "bruin: executable file not found in %PATH%" alors que DAC demarre bien.
set "BRUIN_BIN=%USERPROFILE%\.local\bin"
set "PATH=%PATH%;%BRUIN_BIN%"

echo ============================================
echo   DevoTeam Dashboard - Demarrage
echo ============================================
echo.

if not exist "%BRUIN_BIN%\bruin.exe" (
    echo [ATTENTION] bruin.exe introuvable dans %BRUIN_BIN%
    echo             Installe-le depuis Git Bash :
    echo             curl -LsSf https://getbruin.com/install/dac ^| sh
    echo.
)

REM --- 1. Backend FastAPI (http://127.0.0.1:8000) ---
echo [Backend] demarrage...
start "DevoTeam Backend" cmd /k "cd /d ""%PROJECT_ROOT%"" && python -m uvicorn backend.main:app --reload"

REM --- 2. Dashboards Bruin DAC (http://localhost:8321), affiches en iframe par l'UI ---
REM Le PATH est repropage explicitement a la fenetre fille : dac.exe doit pouvoir
REM appeler "bruin" pour executer le SQL de chaque widget.
echo [DAC] demarrage...
start "DevoTeam DAC" cmd /k "set ""PATH=%PATH%"" && cd /d ""%PROJECT_ROOT%\dac"" && ""%BRUIN_BIN%\dac.exe"" serve --dir . --port 8321"

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
