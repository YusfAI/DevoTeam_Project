@echo off
setlocal
title DevoTeam Dashboard - Lanceur

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

REM Interpreteur Python. scripts\install.bat cree un environnement isole (.venv)
REM pour ne pas installer les versions epinglees a l'echelle de la machine. S'il
REM existe on l'utilise ; sinon on retombe sur le Python du systeme, ce qui garde
REM ce lanceur compatible avec un poste configure avant l'existence du .venv.
set "PY=python"
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"

REM Les binaires Bruin sont installes dans %USERPROFILE%\.local\bin, que l'installeur
REM n'ajoute PAS au PATH systeme. C'est indispensable ici : dac.exe delegue l'execution
REM du SQL a "bruin", qu'il cherche dans le PATH — sans cette ligne, DAC demarre bien
REM mais chaque widget affiche "bruin: executable file not found in %PATH%".
set "BRUIN_BIN=%USERPROFILE%\.local\bin"
set "PATH=%PATH%;%BRUIN_BIN%"

echo ============================================
echo   DevoTeam Dashboard - Demarrage
echo ============================================
echo.

if not exist "%BRUIN_BIN%\bruin.exe" (
    echo [ATTENTION] bruin.exe introuvable dans %BRUIN_BIN%
    echo             Les graphiques resteront vides. Installe-le depuis Git Bash :
    echo             curl -LsSf https://getbruin.com/install/dac ^| sh
    echo.
)

REM Chaque service n'est lance QUE si son port est libre. Sans ce garde-fou, un
REM double-clic sur le raccourci alors que l'app tourne deja laisse l'ancien
REM processus en place (le nouveau ne peut pas prendre le port) : on se retrouve
REM avec un serveur qui repond mais sert du code perime, panne deja rencontree
REM et particulierement penible a diagnostiquer.

REM Forme des lignes « start » ci-dessous : /D fixe le repertoire, /s rend le
REM traitement des guillemets par cmd deterministe, et un seul niveau de
REM guillemets entoure le chemin de l'executable. La forme precedente doublait
REM les guillemets (""%PY%"") et NE DEMARRAIT RIEN des qu'un dossier du chemin
REM contenait une espace — constate sur un poste reel, sans le moindre message.

REM --- 1. Backend FastAPI (http://127.0.0.1:8000) ---
call :is_running 8000
if "%RUNNING%"=="1" (
    echo [Backend]  deja demarre - reutilise.
) else (
    echo [Backend]  demarrage...
    start "DevoTeam Backend" /D "%PROJECT_ROOT%" cmd /s /k ""%PY%" -m uvicorn backend.main:app --reload"
)

REM --- 2. Dashboards Bruin DAC (http://localhost:8321), affiches en iframe par l'UI ---
REM Le PATH est repropage explicitement a la fenetre fille (voir commentaire plus haut).
call :is_running 8321
if "%RUNNING%"=="1" (
    echo [DAC]      deja demarre - reutilise.
) else (
    echo [DAC]      demarrage...
    start "DevoTeam DAC" /D "%PROJECT_ROOT%\dac" cmd /s /k ""%BRUIN_BIN%\dac.exe" serve --dir . --port 8321 --template themes/devoteam.yml"
)

REM --- DAC sombre (port 8322) ---------------------------------------------
REM Un theme DAC est fige au lancement du serveur : il n'existe aucune bascule
REM dans le fichier de theme. Le mode sombre passe donc par un SECOND serveur,
REM qui sert les MEMES dashboards avec la palette sombre. Il est facultatif :
REM s'il ne demarre pas, l'application retombe sur le serveur clair et le
REM tableau de bord reste lisible.
call :is_running 8322
if "%RUNNING%"=="1" (
    echo [DAC-SOMBRE] DAC sombre deja demarre - reutilise.
) else (
    echo [DAC-SOMBRE] Demarrage de DAC sombre...
    start "DevoTeam DAC sombre" /D "%PROJECT_ROOT%\dac" cmd /s /k ""%BRUIN_BIN%\dac.exe" serve --dir . --port 8322 --template themes/devoteam-dark.yml"
)

REM --- 3. Frontend Vite (http://localhost:5173) ---
call :is_running 5173
if "%RUNNING%"=="1" (
    echo [Frontend] deja demarre - reutilise.
) else (
    echo [Frontend] demarrage...
    start "DevoTeam Frontend" /D "%PROJECT_ROOT%\frontend" cmd /s /k "npm run dev"
)

REM --- 4. Ouvrir la page une fois les trois services prets ---
REM 15 s : le frontend est pret en ~3 s, mais la premiere requete d'un widget DAC
REM prend une douzaine de secondes (demarrage a froid du moteur de requete). Ouvrir
REM trop tot afficherait un dashboard vide, qu'on prendrait a tort pour une panne.
echo.
echo Demarrage des services (~15 s)...
timeout /t 15 /nobreak >NUL
start "" "http://localhost:5173"

echo.
echo Tout est lance :
echo   - Interface  http://localhost:5173
echo   - API        http://127.0.0.1:8000
echo   - Dashboards http://localhost:8321
echo.
echo Les serveurs tournent dans leurs propres fenetres (ne pas les fermer).
echo Cette fenetre peut etre fermee.
echo.
pause
endlocal
exit /b 0

REM Positionne RUNNING=1 si le port passe en argument est deja en ecoute.
REM Pas de "-p TCP" ici : ce filtre limite netstat a l'IPv4, or Vite n'ecoute QUE sur
REM l'IPv6 ([::1]:5173). Avec le filtre, le frontend passait pour arrete et etait
REM relance a chaque fois, en doublon.
:is_running
set "RUNNING=0"
netstat -ano | findstr LISTENING | findstr ":%1" >NUL 2>&1
if not errorlevel 1 set "RUNNING=1"
exit /b 0
