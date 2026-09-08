@echo off
setlocal
title DevoTeam Dashboard - Docker

chcp 65001 >NUL

REM ===========================================================================
REM Lanceur du raccourci Bureau pour l'installation DOCKER (voir
REM Documentation/INSTALLATION_DOCKER.md). Sans lui, utiliser Docker demandait
REM d'ouvrir un terminal et de taper "docker compose up -d" a chaque fois — pas
REM un geste raisonnable a demander a quelqu'un qui ne code pas.
REM
REM Ne construit RIEN (pas de --build) : l'image existe deja apres
REM l'installation initiale. Reconstruire a chaque lancement ferait perdre
REM plusieurs minutes pour rien la plupart du temps ; une vraie reconstruction
REM (nouvelle dependance, git pull avec un Dockerfile modifie) reste un geste
REM volontaire, documente a part.
REM ===========================================================================

cd /d "%~dp0.."

where docker >NUL 2>&1
if errorlevel 1 (
    echo.
    echo   [ARRET] Docker introuvable.
    echo           Installer Docker Desktop :
    echo           https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

echo.
echo   ============================================================
echo     DevoTeam Dashboard - Docker
echo   ============================================================
echo.
echo   Demarrage des conteneurs...
docker compose up -d
if errorlevel 1 (
    echo.
    echo   [ARRET] Le demarrage a echoue - voir les messages ci-dessus.
    echo           Docker Desktop est-il bien lance ? Son icone doit etre
    echo           stable dans la zone de notification.
    echo.
    pause
    exit /b 1
)

REM Meme delai que le lanceur natif (start_prod.bat) : le premier chargement
REM d'un widget DAC demande une douzaine de secondes (demarrage a froid du
REM moteur de requetes). Ouvrir plus tot afficherait un tableau de bord vide,
REM qu'on prendrait a tort pour une panne.
echo.
echo   Demarrage de l'application (~15 s)...
timeout /t 15 /nobreak >NUL
start "" "http://127.0.0.1:8000"

echo.
echo   Tout est lance :
echo     - Interface + API   http://127.0.0.1:8000
echo     - Dashboards        http://127.0.0.1:8321
echo.
echo   Les conteneurs continuent de tourner apres la fermeture de cette
echo   fenetre. Pour tout arreter : docker compose down (dans un terminal,
echo   depuis ce dossier).
echo.
pause
endlocal
exit /b 0
