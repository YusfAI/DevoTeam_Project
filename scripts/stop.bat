@echo off
setlocal
title DevoTeam Dashboard - Arret

chcp 65001 >NUL

REM ===========================================================================
REM Le raccourci « Arrêter DevoTeam Dashboard » du Bureau : arrête l'application
REM et libère ce qu'elle occupe, sans ouvrir de terminal ni taper de commande.
REM
REM   1/3  les conteneurs Docker (docker compose down) — libère 8000/8321/8322 ;
REM   2/3  les processus d'une installation native (start_dev.bat, start_prod.bat),
REM        que Docker ne connaît pas — voir scripts\stop.ps1 ;
REM   3/3  la mémoire du modèle de chat (~5 Go), déchargé par l'API d'Ollama.
REM
REM Docker Desktop et Ollama restent lancés en arrière-plan : à vide, ils ne
REM pèsent presque rien, et l'application redémarre alors en une dizaine de
REM secondes par le raccourci « DevoTeam Dashboard (Docker) ».
REM
REM Sans risque à relancer : chaque étape constate d'abord ce qui tourne, et
REM n'arrête que ce qui appartient à l'application.
REM
REM Lignes affichées en ASCII : cmd.exe lit un .bat dans la page de code OEM,
REM quoi que fasse chcp, et rendrait les accents en charabia.
REM ===========================================================================

cd /d "%~dp0.."

echo.
echo   ============================================================
echo     DevoTeam Dashboard - Arret
echo   ============================================================
echo.

REM --- 1/3 : conteneurs Docker ------------------------------------------------
echo   [1/3] Arret de l'application (conteneurs Docker)...
where docker >NUL 2>&1
if errorlevel 1 goto docker_absent
docker info >NUL 2>&1
if errorlevel 1 goto docker_arrete

docker compose down
if errorlevel 1 (
    echo         [ATTENTION] L'arret des conteneurs a echoue - voir ci-dessus.
    set "PROBLEME=1"
) else (
    echo         OK - conteneurs arretes, ports 8000 / 8321 / 8322 liberes.
)
goto natif

:docker_absent
echo         Docker n'est pas installe : rien a arreter de ce cote.
goto natif

:docker_arrete
echo         Docker Desktop n'est pas demarre : aucun conteneur ne tourne.

REM --- 2/3 et 3/3 : processus natifs et memoire du modele ---------------------
:natif
echo.
echo   [2/3] Processus d'une installation sans Docker...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
if errorlevel 1 set "PROBLEME=1"

echo.
if defined PROBLEME (
    echo   ============================================================
    echo     Arret termine, avec un point a verifier ci-dessus.
    echo   ============================================================
    echo.
    pause
    endlocal
    exit /b 1
)

echo   ============================================================
echo     Application arretee - ports et memoire liberes.
echo   ============================================================
echo.
echo     Pour la relancer : raccourci "DevoTeam Dashboard (Docker)".
echo.
echo   Cette fenetre se ferme dans 5 secondes.
REM ping plutot que timeout : timeout refuse une entree redirigee et s'arrete
REM aussitot avec une erreur (meme methode qu'INSTALLER.bat).
ping -n 6 127.0.0.1 >NUL 2>&1
endlocal
exit /b 0
