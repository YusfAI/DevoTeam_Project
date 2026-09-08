@echo off
setlocal
title DevoTeam Dashboard - Assistant d'installation

chcp 65001 >NUL

REM ===========================================================================
REM LE fichier a double-cliquer sur un poste neuf.
REM
REM Il ne fait qu'une chose : lancer l'assistant PowerShell avec la politique
REM d'execution levee pour cette session seule. -ExecutionPolicy Bypass ne
REM modifie AUCUN reglage de la machine, contrairement a Set-ExecutionPolicy :
REM il ne vaut que pour ce processus, ce qui evite de laisser le poste dans un
REM etat different de celui ou on l'a trouve.
REM ===========================================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0assistant.ps1"
set "VERDICT=%ERRORLEVEL%"

echo.
if not "%VERDICT%"=="0" (
    echo   L'installation n'est pas terminee. Relancez ce fichier apres avoir
    echo   corrige les points signales — rien ne sera refait inutilement.
    echo.
)
pause
endlocal
exit /b %VERDICT%
