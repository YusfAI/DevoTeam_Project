@echo off
setlocal EnableDelayedExpansion
title DevoTeam Dashboard - Installation

chcp 65001 >NUL

REM ===========================================================================
REM LE fichier a double-cliquer sur un poste neuf pour installer l'application
REM via Docker, de bout en bout — Docker Desktop et Ollama compris : les deux
REM s'installent tout seuls si absents (winget), sans autre logiciel a poser
REM a la main au prealable. Seul git (pour recuperer le depot avant de lancer
REM ce fichier) reste un prerequis manuel.
REM
REM Ne demande que ce qu'il ne peut pas deviner a votre place : l'identifiant
REM (ou le lien) de la feuille Google et le nom de son onglet — deux questions
REM posees directement en console (etape 5/7). Aucune cle API, aucun compte de
REM service, aucun fichier JSON : la lecture du Sheet se fait par son lien
REM d'export public. Tout le reste — Docker, Ollama, construction, demarrage,
REM raccourci Bureau, verification finale — est automatique.
REM
REM Rejouable sans risque : chaque etape verifie d'abord si elle est deja
REM faite. Le relancer apres avoir renseigne .env (ou apres avoir installe
REM Docker/redemarre Windows) reprend exactement la ou ca s'etait arrete,
REM sans rien refaire ni rien perdre.
REM
REM IMPORTANT : le nom de l'onglet doit etre EXACT. Un nom incorrect ne produit
REM PAS d'erreur -- Google charge alors silencieusement le premier onglet de la
REM feuille a la place, sans le moindre avertissement.
REM
REM Le modele de chat (Ollama) tourne sur la machine HOTE, pas dans un
REM conteneur (etape 4/7 ci-dessous) — docker-compose.yml route le backend
REM vers lui via host.docker.internal. Sous Docker Desktop (Windows), cette
REM adresse joint bien un Ollama ecoutant sur 127.0.0.1 : le trafic passe par
REM la passerelle de Docker Desktop. Aucune variable OLLAMA_HOST a poser.
REM ===========================================================================

cd /d "%~dp0"

echo.
echo   ============================================================
echo     DevoTeam Dashboard - Installation
echo   ============================================================
echo.
echo   Ce script installe tout automatiquement. Il vous demandera juste
echo   deux valeurs, en console :
echo     - l'identifiant ^(ou le lien^) de la feuille Google
echo     - le nom de l'onglet
echo   Aucune cle API, aucun compte de service, aucun JSON a deposer.
echo.
echo   Liens et etapes detaillees pour les obtenir :
echo     Documentation\OBTENIR_LES_ACCES.md
echo.
pause

REM --- 1/7 : le dossier est-il exploitable ? ----------------------------------
REM Le .git n'est pas un detail d'organisation ici : le moteur de tableaux de
REM bord (dac, qui appelle bruin) REFUSE de lancer la moindre requete s'il ne
REM trouve pas de racine de depot Git en remontant depuis /app. Verifie en
REM conditions reelles : meme dossier, meme .bruin.yml, meme donnees — avec
REM .git la connexion DuckDB repond « connected », sans .git elle repond
REM « bruin query failed ». Un dossier obtenu par « Download ZIP » sur GitHub
REM n'a PAS de .git : l'application s'installerait et demarrerait normalement,
REM mais tous les tableaux de bord resteraient vides. Mieux vaut l'arreter ici,
REM avec le geste exact a faire, que de laisser decouvrir ca en demonstration.
echo.
echo   [1/7] Verification du dossier...
if not exist ".git" (
    echo.
    echo   [ARRET] Ce dossier n'est pas un clone Git ^(pas de .git^).
    echo.
    echo           C'est le cas si le projet a ete recupere par le bouton
    echo           « Download ZIP » de GitHub. Les tableaux de bord ne
    echo           fonctionneraient pas : le moteur de requetes exige un
    echo           depot Git.
    echo.
    echo           A faire : supprimer ce dossier et le recuperer ainsi,
    echo           dans une invite de commandes :
    echo             git clone https://github.com/YusfAI/DevoTeam_Project.git
    echo             cd DevoTeam_Project
    echo             git checkout Version_2
    echo.
    echo           Puis relancer ce fichier depuis le dossier obtenu.
    echo.
    pause
    exit /b 1
)
if not exist ".env.example" (
    echo.
    echo   [ARRET] Fichier .env.example introuvable — ce dossier n'est pas
    echo           une copie complete du projet. Refaites le git clone.
    echo.
    pause
    exit /b 1
)
echo         OK - clone Git complet

REM La memoire n'est pas bloquante mais elle change l'experience : le modele
REM de chat occupe ~5 Go a lui seul. En dessous de 16 Go, Windows + Docker +
REM le modele se disputent la RAM et les reponses deviennent tres lentes.
for /f %%m in ('powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)" 2^>NUL') do set "RAM_GO=%%m"
if defined RAM_GO (
    if !RAM_GO! LSS 16 (
        echo         ATTENTION : !RAM_GO! Go de RAM detectes. L'application
        echo         fonctionnera, mais le modele de chat ^(~5 Go^) sera lent.
        echo         16 Go est le confort recommande.
    ) else (
        echo         OK - !RAM_GO! Go de RAM
    )
)

REM --- 2/7 : Docker est-il installe ? -----------------------------------------
echo.
echo   [2/7] Verification de Docker...
where docker >NUL 2>&1
if errorlevel 1 (
    echo         MANQUANT. Installation automatique via winget...
    where winget >NUL 2>&1
    if errorlevel 1 (
        echo.
        echo   [ARRET] winget indisponible sur ce poste ^(Windows trop ancien^).
        echo           Installez Docker Desktop manuellement, puis relancez :
        echo           https://www.docker.com/products/docker-desktop/
        echo.
        pause
        exit /b 1
    )
    winget install --id Docker.DockerDesktop -e --silent --accept-package-agreements --accept-source-agreements
    echo.
    echo   Docker Desktop installe. Une derniere etape MANUELLE, obligatoire :
    echo     1. Windows demande peut-etre a REDEMARRER ^(activation de WSL2^) —
    echo        faites-le si c'est le cas.
    echo     2. Lancez « Docker Desktop » depuis le menu Demarrer une premiere
    echo        fois ^(accepter les conditions d'utilisation^).
    echo     3. Relancez ce fichier — il reprendra exactement ici, sans rien
    echo        refaire de ce qui precede.
    echo.
    pause
    exit /b 1
)
echo         OK

REM --- 3/7 : Docker Desktop est-il DEMARRE ? ----------------------------------
REM "docker" present ne veut pas dire "Docker Desktop demarre" : c'est l'erreur
REM la plus frequente d'un premier lancement. On attend plutot que d'echouer
REM immediatement — jusqu'a une minute, le temps de le lancer depuis le menu
REM Demarrer si ce n'est pas deja fait.
echo.
echo   [3/7] Verification que Docker est demarre...
set "TENTATIVES=0"
:attendre_docker
docker info >NUL 2>&1
if not errorlevel 1 goto docker_pret
set /a TENTATIVES+=1
if !TENTATIVES!==1 (
    echo         En attente de Docker Desktop...
    echo         ^(Lancez-le depuis le menu Demarrer s'il ne l'est pas deja^)
)
if !TENTATIVES! GEQ 30 (
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

REM --- 4/7 : Ollama (modele de chat local) --------------------------------------
REM Tourne sur la machine HOTE, pas dans un conteneur (voir l'en-tete du
REM fichier) : verifie ici, avant docker compose, comme les autres prerequis.
echo.
echo   [4/7] Modele de chat local ^(Ollama^)...
set "OLLAMA_EXE=ollama"
where ollama >NUL 2>&1
if errorlevel 1 (
    echo         MANQUANT. Installation automatique via winget...
    where winget >NUL 2>&1
    if errorlevel 1 (
        echo.
        echo   [ARRET] winget indisponible sur ce poste ^(Windows trop ancien^).
        echo           Installez Ollama manuellement, puis relancez :
        echo           https://ollama.com/download
        echo.
        pause
        exit /b 1
    )
    winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements
    REM Le PATH de CETTE fenetre reste celui d'avant l'installation : winget
    REM met a jour le registre, pas les processus deja lances. On vise donc
    REM l'executable a son emplacement connu plutot que de compter sur "where".
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    ) else if exist "%ProgramFiles%\Ollama\ollama.exe" (
        set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
    ) else (
        echo.
        echo   [ARRET] Ollama installe mais introuvable. Fermez cette fenetre,
        echo           rouvrez-en une nouvelle et relancez ce fichier.
        echo.
        pause
        exit /b 1
    )
    echo         OK - Ollama installe
) else (
    echo         OK - Ollama installe
)

REM Installe ne veut pas dire DEMARRE : le service peut etre arrete (poste
REM redemarre sans lancement automatique, ou installation silencieuse qui n'a
REM pas encore demarre le service). Sans lui, "pull" echoue et le chat reste
REM muet une fois l'application lancee. On le demarre plutot que d'echouer.
REM Boucle d'attente ecrite a plat, sans bloc entre parentheses : une etiquette
REM (:attendre_ollama) placee a l'interieur d'un bloc ( ... ) n'est pas
REM analysable par cmd.exe — meme raison qui impose ce style aux deux autres
REM boucles de ce fichier.
curl -s -m 3 -o NUL http://127.0.0.1:11434/api/tags 2>NUL
if not errorlevel 1 goto ollama_pret
echo         Service Ollama arrete - demarrage...
start "" /b "!OLLAMA_EXE!" serve
set "TENTATIVES=0"
:attendre_ollama
ping -n 3 127.0.0.1 >NUL 2>&1
curl -s -m 3 -o NUL http://127.0.0.1:11434/api/tags 2>NUL
if not errorlevel 1 goto ollama_pret
set /a TENTATIVES+=1
if !TENTATIVES! GEQ 15 (
    echo.
    echo   [ARRET] Le service Ollama ne repond pas sur le port 11434.
    echo           Lancez « Ollama » depuis le menu Demarrer, puis
    echo           relancez ce fichier.
    echo.
    pause
    exit /b 1
)
goto attendre_ollama
:ollama_pret
echo         OK - service Ollama en ligne

"!OLLAMA_EXE!" list 2>NUL | findstr /C:"qwen2.5" >NUL
if errorlevel 1 (
    echo         Modele absent - telechargement de qwen2.5:7b-instruct-q4_K_M
    echo         ^(~4.7 Go, plusieurs minutes selon la connexion^)...
    "!OLLAMA_EXE!" pull qwen2.5:7b-instruct-q4_K_M
    if errorlevel 1 (
        echo.
        echo   [ARRET] Le telechargement du modele a echoue. Reessayez :
        echo             ollama pull qwen2.5:7b-instruct-q4_K_M
        echo.
        pause
        exit /b 1
    )
)
echo         OK - modele present

REM --- 5/7 : .env --------------------------------------------------------------
REM Deux valeurs demandees ICI, en console (set /p) plutot que par le Bloc-notes :
REM plus rapide, un seul enchainement de questions. Aucune n'est un secret --
REM la lecture du Sheet ne demande plus de cle API du tout (lien d'export public).
echo.
echo   [5/7] Configuration (feuille Google)...
if not exist ".env" (
    copy /y ".env.example" ".env" >NUL
    echo         .env cree a partir du modele.
)

set "CUR_ID="
set "CUR_TAB="
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if "%%a"=="GOOGLE_SHEET_ID" set "CUR_ID=%%b"
    if "%%a"=="GOOGLE_SHEET_TAB" set "CUR_TAB=%%b"
)

echo.
echo         Deux valeurs necessaires ^(Entree conserve la valeur actuelle^) :
echo.
set /p "GOOGLE_SHEET_ID=  Identifiant ou lien de la feuille [%CUR_ID%] : "
if not defined GOOGLE_SHEET_ID set "GOOGLE_SHEET_ID=%CUR_ID%"

set "DEFAUT_TAB=%CUR_TAB%"
if "%DEFAUT_TAB%"=="" set "DEFAUT_TAB=opportunities"
echo         IMPORTANT : le nom de l'onglet doit etre EXACT -- un nom incorrect
echo         ne produit pas d'erreur, il charge silencieusement le premier
echo         onglet de la feuille a la place.
set /p "GOOGLE_SHEET_TAB=  Nom de l'onglet [%DEFAUT_TAB%] : "
if not defined GOOGLE_SHEET_TAB set "GOOGLE_SHEET_TAB=%DEFAUT_TAB%"

if "%GOOGLE_SHEET_ID%"=="" (
    echo.
    echo   [ARRET] L'identifiant de la feuille est obligatoire.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\maj_env.ps1"
if errorlevel 1 (
    echo.
    echo   [ARRET] Echec de l'ecriture dans .env.
    echo.
    pause
    exit /b 1
)
echo.
echo         OK - .env mis a jour
echo.
echo         Facultatif ^(rappel quotidien des echeances par email^) : ouvrez
echo         .env vous-meme pour renseigner GMAIL_SENDER / GMAIL_APP_PASSWORD /
echo         ALERT_RECIPIENT_EMAIL. Sans elles, l'application fonctionne
echo         integralement, seul ce rappel ne part pas.

REM --- 6/7 : construction et demarrage ------------------------------------------
REM Les trois ports sont publies sur 127.0.0.1 (voir docker-compose.yml). S'ils
REM sont deja pris par un AUTRE programme, "docker compose up" echoue sur un
REM message de bas niveau ("bind: address already in use") qui ne dit pas quoi
REM faire. On regarde avant — mais seulement si ce projet n'a pas deja ses
REM propres conteneurs en route, sinon un simple relancement se bloquerait
REM lui-meme sur ses ports a lui.
echo.
echo   [6/7] Construction et demarrage ^(plusieurs minutes la premiere fois^)...
set "DEJA_LANCE="
for /f %%c in ('docker compose ps -q 2^>NUL') do set "DEJA_LANCE=1"
if not defined DEJA_LANCE (
    powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000,8321,8322 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >NUL 2>&1
    if errorlevel 1 (
        echo.
        echo   [ARRET] Un des ports 8000 / 8321 / 8322 est deja utilise par un
        echo           autre programme sur ce poste.
        echo.
        echo           Fermez-le, puis relancez ce fichier. Pour savoir lequel :
        echo             netstat -ano ^| findstr "8000 8321 8322"
        echo.
        pause
        exit /b 1
    )
)
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo   [ARRET] Le demarrage a echoue - voir les messages ci-dessus.
    echo.
    pause
    exit /b 1
)
echo         OK

REM --- 7/7 : raccourci Bureau ----------------------------------------------------
echo.
echo   [7/7] Raccourci sur le Bureau...
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
if !TENTATIVES! GEQ 30 (
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
echo     La premiere question posee au chat est plus lente que les
echo     suivantes : le modele se charge en memoire a ce moment-la.
echo     Sans carte graphique dediee, comptez quelques dizaines de
echo     secondes par reponse — c'est normal, pas une panne.
echo.
echo     Prochains lancements : raccourci "DevoTeam Dashboard (Docker)"
echo     sur le Bureau.
echo.
pause
endlocal
exit /b 0
