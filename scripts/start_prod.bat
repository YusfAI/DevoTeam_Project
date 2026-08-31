@echo off
setlocal
title DevoTeam Dashboard - Production

REM ===========================================================================
REM Lanceur de PRODUCTION. Difference avec start_dev.bat :
REM
REM   - le frontend est COMPILE puis servi par le backend lui-meme
REM     (backend/main.py monte frontend/dist sur "/"), il n'y a donc PAS de
REM     serveur Vite ; tout passe par le port 8000, en meme origine, et le proxy
REM     de developpement ne joue plus aucun role.
REM   - uvicorn tourne SANS --reload : le rechargement a chaud surveille tous les
REM     fichiers du projet et redemarre le serveur des qu'un octet bouge. En
REM     production c'est du travail perdu, et un redemarrage au mauvais moment
REM     coupe une requete en cours.
REM
REM Deux services au lieu de trois : l'interface et l'API sur 8000, les
REM dashboards sur 8321.
REM ===========================================================================

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

REM Meme raison que dans start_dev.bat : dac.exe delegue l'execution du SQL a
REM "bruin", qu'il cherche dans le PATH, et l'installeur n'ajoute pas
REM %USERPROFILE%\.local\bin au PATH systeme.
set "BRUIN_BIN=%USERPROFILE%\.local\bin"
set "PATH=%PATH%;%BRUIN_BIN%"

echo ============================================
echo   DevoTeam Dashboard - Production
echo ============================================
echo.

if not exist "%BRUIN_BIN%\bruin.exe" (
    echo [ARRET] bruin.exe introuvable dans %BRUIN_BIN%
    echo         Sans lui, DAC demarre mais tous les visuels restent en erreur.
    echo         Installe-le depuis Git Bash :
    echo             curl -LsSf https://getbruin.com/install/dac ^| sh
    echo.
    pause
    exit /b 1
)

REM --- 1. Compiler le frontend -----------------------------------------------
REM AVANT de lancer quoi que ce soit : le backend sert frontend/dist tel qu'il le
REM trouve. Demarrer sur une compilation ratee ou perimee afficherait l'ancienne
REM version de l'interface sans le moindre signe que quelque chose a echoue.
echo [1/3] Compilation du frontend...
pushd "%PROJECT_ROOT%\frontend"
call npm run build
if errorlevel 1 (
    popd
    echo.
    echo [ARRET] La compilation du frontend a echoue. Rien n'a ete demarre.
    echo         Corrige l'erreur ci-dessus puis relance ce script.
    pause
    exit /b 1
)
popd
echo       OK
echo.

REM --- 2. Dashboards Bruin DAC (http://localhost:8321) -----------------------
call :is_running 8321
if "%RUNNING%"=="1" (
    echo [2/3] DAC deja demarre - reutilise.
) else (
    echo [2/3] Demarrage de DAC...
    start "DevoTeam DAC" cmd /k "set ""PATH=%PATH%"" && cd /d ""%PROJECT_ROOT%\dac"" && ""%BRUIN_BIN%\dac.exe"" serve --dir . --port 8321 --template themes/devoteam.yml"
)

REM --- 3. Backend + interface compilee (http://127.0.0.1:8000) ---------------
REM UN SEUL worker, volontairement. Le jeu de donnees vit en memoire dans le
REM processus (backend/data_store.py) et un planificateur y tourne : avec
REM plusieurs workers, chacun garderait sa propre copie des donnees ET relancerait
REM le planificateur — d'ou des emails d'alerte envoyes en double et des ecritures
REM concurrentes dans le Google Sheet. Le goulot n'est de toute facon pas le
REM backend (mesure : 0,03 s par question) mais le quota du modele.
call :is_running 8000
if "%RUNNING%"=="1" (
    echo [3/3] Backend deja demarre - reutilise.
) else (
    echo [3/3] Demarrage du backend...
    start "DevoTeam Backend" cmd /k "cd /d ""%PROJECT_ROOT%"" && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1"
)

REM --- Ouvrir la page une fois les services prets -----------------------------
REM Le premier chargement d'un widget DAC demande une douzaine de secondes
REM (demarrage a froid du moteur de requete). Ouvrir plus tot afficherait un
REM tableau de bord vide, qu'on prendrait a tort pour une panne.
echo.
echo Demarrage des services (~15 s)...
timeout /t 15 /nobreak >NUL
start "" "http://127.0.0.1:8000"

echo.
echo Tout est lance :
echo   - Interface + API  http://127.0.0.1:8000
echo   - Dashboards       http://localhost:8321
echo.
echo Les serveurs tournent dans leurs propres fenetres (ne pas les fermer).
echo Cette fenetre peut etre fermee.
echo.
pause
endlocal
exit /b 0

REM Positionne RUNNING=1 si le port passe en argument est deja en ecoute.
:is_running
set "RUNNING=0"
netstat -ano | findstr LISTENING | findstr ":%1" >NUL 2>&1
if not errorlevel 1 set "RUNNING=1"
exit /b 0
