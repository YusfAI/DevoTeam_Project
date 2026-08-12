@echo off
setlocal
title DevoTeam Dashboard - Lanceur

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

echo ============================================
echo   DevoTeam Dashboard - Demarrage
echo ============================================
echo.

REM --- 1. MySQL (XAMPP) ---
tasklist /FI "IMAGENAME eq mysqld.exe" 2>NUL | find /I "mysqld.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [MySQL] deja demarre.
) else (
    if exist "C:\xampp\XAampp\mysql_start.bat" (
        echo [MySQL] demarrage via XAMPP...
        start "XAMPP MySQL" "C:\xampp\XAampp\mysql_start.bat"
        timeout /t 3 /nobreak >NUL
    ) else (
        echo [MySQL] introuvable a l'emplacement attendu.
        echo         Demarre-le manuellement via le panneau de controle XAMPP.
    )
)

REM --- 2. Backend FastAPI (http://127.0.0.1:8000) ---
echo [Backend] demarrage...
start "DevoTeam Backend" cmd /k "cd /d ""%PROJECT_ROOT%"" && python -m uvicorn backend.main:app --reload"

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
