@echo off
setlocal EnableDelayedExpansion
title DevoTeam Dashboard - acces public (ngrok)

chcp 65001 >NUL

REM ===========================================================================
REM Expose l'application sur une URL publique, pour la faire essayer a distance.
REM
REM DEUX tunnels, et non un seul. Le tableau de bord est charge en iframe par le
REM NAVIGATEUR : lui donner « 127.0.0.1:8321 » revient a lui faire interroger SA
REM PROPRE machine. Avec un seul tunnel, le chat repond et tous les tableaux de
REM bord restent vides, sans qu'une seule requete echoue.
REM
REM DAC ne sait pas servir sous un prefixe de chemin (verifie : « dac serve » n'a
REM aucune option de base path, et il sert ses ressources en chemins absolus).
REM Il lui faut donc sa propre origine, donc son propre tunnel.
REM
REM L'adresse publique de DAC est transmise au backend par DAC_PUBLIC_URL, lu a
REM l'EXECUTION : une URL de tunnel change a chaque session, recompiler le
REM frontend pour cela n'aurait aucun sens.
REM ===========================================================================

cd /d "%~dp0.."
set "RACINE=%CD%"

where ngrok >NUL 2>&1
if errorlevel 1 (
    echo.
    echo   [ARRET] ngrok introuvable.
    echo           https://ngrok.com/download  puis  ngrok config add-authtoken VOTRE_JETON
    echo.
    pause
    exit /b 1
)

echo.
echo   ============================================================
echo     Acces public - DevoTeam Dashboard
echo   ============================================================
echo.
echo   AVANT DE CONTINUER
echo.
echo   Cette URL rend les donnees commerciales accessibles a QUICONQUE
echo   la possede. Elle n'est pas secrete : traitez-la comme un mot de
echo   passe, et arretez les tunnels des que l'essai est termine.
echo.
echo   Protection recommandee, dans ngrok.yml :
echo       basic_auth: ["utilisateur:motdepasse"]
echo.
pause

REM --- 1. Le tunnel des tableaux de bord -------------------------------------
echo.
echo   [1/3] Tunnel des tableaux de bord (port 8321)...
start "ngrok DAC" cmd /k "ngrok http 8321 --log stdout"

echo.
echo   Ouvrez http://127.0.0.1:4040 et relevez l'URL du tunnel 8321,
echo   puis collez-la ci-dessous (elle ressemble a https://xxxx.ngrok-free.app).
echo.
set /p "DAC_PUBLIC_URL=  URL publique de DAC : "

if "%DAC_PUBLIC_URL%"=="" (
    echo.
    echo   [ARRET] Sans cette adresse, les tableaux de bord resteraient vides.
    echo.
    pause
    exit /b 1
)

REM --- 2. Le backend, qui transmettra cette adresse au navigateur -------------
echo.
echo   [2/3] Redemarrage du backend avec l'adresse publique...
set "PY=python"
if exist "%RACINE%\.venv\Scripts\python.exe" set "PY=%RACINE%\.venv\Scripts\python.exe"

start "DevoTeam Backend (public)" cmd /k "cd /d ""%RACINE%"" && set ""DAC_PUBLIC_URL=%DAC_PUBLIC_URL%"" && ""%PY%"" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1"

REM --- 3. Le tunnel de l'application -----------------------------------------
echo.
echo   [3/3] Tunnel de l'application (port 8000)...
start "ngrok application" cmd /k "ngrok http 8000 --log stdout"

echo.
echo   ============================================================
echo     Les deux tunnels tournent. Relevez l'URL du port 8000 sur
echo     http://127.0.0.1:4040 : c'est celle a partager.
echo.
echo     PREMIERE VISITE : ngrok affiche une page d'avertissement.
echo     Ouvrez D'ABORD l'URL de DAC dans un onglet et cliquez
echo     « Visit Site », sinon l'iframe affichera cette page a la
echo     place des tableaux de bord.
echo   ============================================================
echo.
pause
endlocal
exit /b 0
