@echo off
setlocal EnableDelayedExpansion
title DevoTeam Dashboard - Installation

chcp 65001 >NUL

REM ===========================================================================
REM LE fichier a double-cliquer sur un poste neuf pour installer l'application
REM via Docker, de bout en bout.
REM
REM Ne demande que deux choses qu'il ne peut pas deviner a votre place :
REM   - le fichier .env (cle Gemini, feuille Google) ;
REM   - le fichier credentials\google_service_account.json.
REM Tout le reste — verification de Docker, construction, demarrage, raccourci
REM Bureau, verification finale — est automatique.
REM
REM Rejouable sans risque : chaque etape verifie d'abord si elle est deja
REM faite. Le relancer apres avoir complete .env ou le JSON reprend exactement
REM la ou ca s'etait arrete, sans rien refaire ni rien perdre.
REM
REM Ne demande AUCUN secret au clavier : .env s'ouvre dans le Bloc-notes, une
REM cle tapee dans une console resterait dans son historique.
REM ===========================================================================

cd /d "%~dp0"

echo.
echo   ============================================================
echo     DevoTeam Dashboard - Installation
echo   ============================================================
echo.
echo   Ce script installe tout automatiquement. Il ne vous demandera
echo   que deux choses a completer vous-meme :
echo     - le fichier .env                      (cle Gemini, feuille Google)
echo     - credentials\google_service_account.json
echo.
echo   Liens et etapes detaillees pour les obtenir :
echo     Documentation\OBTENIR_LES_ACCES.md
echo.
pause

REM --- 1/6 : Docker est-il installe ? -----------------------------------------
echo.
echo   [1/6] Verification de Docker...
where docker >NUL 2>&1
if errorlevel 1 (
    echo.
    echo   [ARRET] Docker n'est pas installe sur ce poste.
    echo           Installez Docker Desktop, puis relancez ce fichier :
    echo           https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)
echo         OK

REM --- 2/6 : Docker Desktop est-il DEMARRE ? ----------------------------------
REM "docker" present ne veut pas dire "Docker Desktop demarre" : c'est l'erreur
REM la plus frequente d'un premier lancement. On attend plutot que d'echouer
REM immediatement — jusqu'a une minute, le temps de le lancer depuis le menu
REM Demarrer si ce n'est pas deja fait.
echo.
echo   [2/6] Verification que Docker est demarre...
set "TENTATIVES=0"
:attendre_docker
docker info >NUL 2>&1
if not errorlevel 1 goto docker_pret
set /a TENTATIVES+=1
if %TENTATIVES%==1 (
    echo         En attente de Docker Desktop...
    echo         ^(Lancez-le depuis le menu Demarrer s'il ne l'est pas deja^)
)
if %TENTATIVES% GEQ 30 (
    echo.
    echo   [ARRET] Docker Desktop ne repond toujours pas apres une minute.
    echo           Lancez-le, attendez son icone stable dans la zone de
    echo           notification, puis relancez ce fichier.
    echo.
    pause
    exit /b 1
)
ping -n 3 127.0.0.1 >NUL 2>&1
goto attendre_docker
:docker_pret
echo         OK

REM --- 3/6 : .env --------------------------------------------------------------
echo.
echo   [3/6] Fichier de configuration (.env)...
if not exist ".env" (
    copy /y ".env.example" ".env" >NUL
    echo         .env cree a partir du modele.
    echo.
    echo         Le Bloc-notes va s'ouvrir : renseignez au minimum
    echo           GOOGLE_API_KEY, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB
    echo         puis ENREGISTREZ ^(Ctrl+S^) et fermez le Bloc-notes.
    echo.
    pause
    notepad ".env"
    echo.
    echo   Appuyez sur une touche une fois .env enregistre et ferme.
    pause
) else (
    echo         OK - deja present
)

REM --- 4/6 : credentials\google_service_account.json ---------------------------
echo.
echo   [4/6] Compte de service Google...
if not exist "credentials" mkdir "credentials"
if not exist "credentials\google_service_account.json" (
    echo         Fichier absent.
    echo.
    echo         Le dossier va s'ouvrir : deposez-y le fichier JSON du compte
    echo         de service Google, renomme EXACTEMENT :
    echo           google_service_account.json
    echo.
    pause
    start "" "credentials"
    echo.
    echo   Appuyez sur une touche une fois le fichier depose.
    pause
) else (
    echo         OK - deja present
)

REM --- 5/6 : construction et demarrage ------------------------------------------
echo.
echo   [5/6] Construction et demarrage ^(plusieurs minutes la premiere fois^)...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo   [ARRET] Le demarrage a echoue - voir les messages ci-dessus.
    echo.
    pause
    exit /b 1
)
echo         OK

REM --- 6/6 : raccourci Bureau ----------------------------------------------------
echo.
echo   [6/6] Raccourci sur le Bureau...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create_shortcut.ps1" >NUL 2>&1
if errorlevel 1 (
    echo         Le raccourci n'a pas pu etre cree - sans consequence.
    echo         Prochain lancement : docker compose up -d
) else (
    echo         OK
)

REM Attente ACTIVE plutot qu'un delai fixe : un premier demarrage apres
REM reconstruction peut prendre plus ou moins de temps que les ~15 s habituels
REM ^(chargement initial de la feuille Google, moteur de requetes qui demarre a
REM froid^). Interroger /health jusqu'a ce qu'il reponde evite de lancer la
REM verification finale sur une application pas encore prete.
echo.
echo   Demarrage de l'application...
set "TENTATIVES=0"
:attendre_app
curl -s -o NUL -w "%%{http_code}" http://127.0.0.1:8000/health > "%TEMP%\devoteam_health.txt" 2>NUL
set /p CODE_SANTE=<"%TEMP%\devoteam_health.txt"
if "%CODE_SANTE%"=="200" goto app_prete
set /a TENTATIVES+=1
if %TENTATIVES% GEQ 30 (
    echo         Toujours pas prete apres une minute - la verification qui
    echo         suit peut echouer une premiere fois ; relancez-la alors :
    echo           docker compose exec -e TEST_DAC_URL=http://dac-light:8321 backend python scripts/test_fonctionnel.py
    goto app_prete
)
ping -n 3 127.0.0.1 >NUL 2>&1
goto attendre_app
:app_prete
del "%TEMP%\devoteam_health.txt" >NUL 2>&1
start "" "http://127.0.0.1:8000"

echo.
echo   ============================================================
echo     VERIFICATION - les chiffres affiches sont-ils justes ?
echo   ============================================================
echo.
echo   Calcule la reponse attendue depuis VOS donnees et la compare a ce
echo   que l'application annonce reellement — execute a l'interieur du
echo   conteneur, aucun Python local necessaire.
echo.
docker compose exec -e TEST_DAC_URL=http://dac-light:8321 backend python scripts/test_fonctionnel.py
echo.

echo   ============================================================
echo     INSTALLATION TERMINEE
echo   ============================================================
echo.
echo     - Interface + API   http://127.0.0.1:8000
echo     - Dashboards        http://127.0.0.1:8321
echo.
echo     Si la verification ci-dessus n'affiche PAS "TOUT EST JUSTE",
echo     ne presentez pas l'application avant d'avoir corrige ce qui
echo     est signale.
echo.
echo     Prochains lancements : raccourci "DevoTeam Dashboard (Docker)"
echo     sur le Bureau.
echo.
pause
endlocal
exit /b 0
