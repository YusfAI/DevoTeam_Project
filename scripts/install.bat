@echo off
setlocal EnableDelayedExpansion
title DevoTeam Dashboard - Installation

REM Console en UTF-8. Sans cela, les accents du script de verification sortent en
REM "?" sur une console francaise (page de code 850), ce qui rend illisible
REM justement le texte qu'on lit quand quelque chose ne va pas.
chcp 65001 >NUL

REM ===========================================================================
REM Installation sur un poste neuf.
REM
REM Ecrit pour etre relance sans risque : chaque etape verifie d'abord si elle a
REM deja ete faite. Une installation qui echoue au milieu se reprend en relancant
REM ce script, sans avoir a defaire quoi que ce soit.
REM
REM Ce qu'il NE fait pas, volontairement :
REM   - il n'installe ni Python ni Node (telechargements qui demandent des droits
REM     administrateur et une intervention humaine) : il les detecte et dit ou les
REM     prendre ;
REM   - il ne demande AUCUN secret en console. Les cles se saisissent dans le
REM     fichier .env, ouvert dans le Bloc-notes : une cle tapee dans une console
REM     reste dans son historique.
REM ===========================================================================

cd /d "%~dp0.."
set "RACINE=%CD%"
set "BLOQUANT=0"

echo.
echo   ============================================================
echo     DevoTeam Dashboard - Installation
echo   ============================================================
echo.

REM --- 1. Python -------------------------------------------------------------
echo   [1/7] Python...
where python >NUL 2>&1
if errorlevel 1 (
    echo         MANQUANT. Installer Python 3.11 ou plus recent :
    echo           https://www.python.org/downloads/
    echo         IMPORTANT : cocher "Add python.exe to PATH" pendant l'installation.
    set "BLOQUANT=1"
    goto :fin
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo         OK - Python !PYVER!

REM --- 2. Node.js ------------------------------------------------------------
echo   [2/7] Node.js...
where npm >NUL 2>&1
if errorlevel 1 (
    echo         MANQUANT. Installer Node.js LTS :
    echo           https://nodejs.org/
    echo         Il sert a compiler l'interface, une seule fois.
    set "BLOQUANT=1"
    goto :fin
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do set "NODEVER=%%v"
echo         OK - Node !NODEVER!

REM --- 3. Environnement Python isole -----------------------------------------
REM Un environnement virtuel plutot que le Python du systeme : les versions sont
REM EPINGLEES (requirements.txt), et les installer a l'echelle de la machine
REM pourrait casser un autre outil deja present sur le poste.
echo   [3/7] Environnement Python et dependances...
if not exist "%RACINE%\.venv\Scripts\python.exe" (
    python -m venv "%RACINE%\.venv"
    if errorlevel 1 (
        echo         ECHEC de la creation de l'environnement virtuel.
        set "BLOQUANT=1"
        goto :fin
    )
    echo         environnement cree
)
"%RACINE%\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
"%RACINE%\.venv\Scripts\python.exe" -m pip install --quiet -r "%RACINE%\requirements.txt"
if errorlevel 1 (
    echo         ECHEC de l'installation des dependances Python.
    set "BLOQUANT=1"
    goto :fin
)
echo         OK - dependances installees

REM --- 4. Interface ----------------------------------------------------------
echo   [4/7] Compilation de l'interface...
pushd "%RACINE%\frontend"
if not exist "node_modules" (
    echo         installation des paquets ^(quelques minutes^)...
    call npm install --silent
    if errorlevel 1 (
        popd
        echo         ECHEC de npm install.
        set "BLOQUANT=1"
        goto :fin
    )
)
call npm run build
if errorlevel 1 (
    popd
    echo         ECHEC de la compilation.
    set "BLOQUANT=1"
    goto :fin
)
popd
echo         OK - interface compilee

REM --- 5. Moteur de tableaux de bord -----------------------------------------
REM dac.exe delegue l'execution du SQL a bruin.exe, qu'il cherche dans le PATH.
REM Sans lui, DAC demarre normalement et CHAQUE visuel echoue separement : la
REM panne la plus deroutante de toute l'installation.
echo   [5/7] Moteur de tableaux de bord ^(Bruin DAC^)...
set "BRUIN_BIN=%USERPROFILE%\.local\bin"
if exist "%BRUIN_BIN%\dac.exe" if exist "%BRUIN_BIN%\bruin.exe" (
    echo         OK - deja installe
    goto :apres_dac
)
echo         MANQUANT. A installer depuis Git Bash ^(livre avec Git pour Windows^) :
echo.
echo             curl -LsSf https://getbruin.com/install/dac ^| sh
echo.
echo         Si Git Bash n'est pas installe : https://git-scm.com/download/win
echo         Relancer ce script ensuite.
set "BLOQUANT=1"
:apres_dac

REM --- 6. Configuration ------------------------------------------------------
echo   [6/7] Configuration...
if not exist "%RACINE%\credentials" mkdir "%RACINE%\credentials"

if not exist "%RACINE%\.env" (
    copy /y "%RACINE%\.env.example" "%RACINE%\.env" >NUL
    echo         .env cree a partir du modele.
    echo.
    echo         Le Bloc-notes va s'ouvrir : renseigner les valeurs, ENREGISTRER,
    echo         puis fermer la fenetre pour continuer.
    echo.
    pause
    notepad "%RACINE%\.env"
) else (
    echo         OK - .env deja present
)

REM --- 7. Raccourcis ---------------------------------------------------------
echo   [7/7] Raccourcis du Bureau...
powershell -ExecutionPolicy Bypass -NoProfile -File "%RACINE%\scripts\create_shortcut.ps1" >NUL 2>&1
if errorlevel 1 (
    echo         ECHEC - les raccourcis n'ont pas ete crees.
) else (
    echo         OK - deux raccourcis crees
)

:fin
echo.
echo   ============================================================
if "%BLOQUANT%"=="1" (
    echo     INSTALLATION INCOMPLETE
    echo     Corriger le point signale ci-dessus, puis relancer ce script.
    echo   ============================================================
    echo.
    pause
    exit /b 1
)

echo     Verification finale...
echo   ============================================================
"%RACINE%\.venv\Scripts\python.exe" "%RACINE%\scripts\verifier_installation.py"
set "VERDICT=%ERRORLEVEL%"

echo.
if "%VERDICT%"=="0" (
    echo   Installation terminee. Lancer l'application par le raccourci
    echo   "DevoTeam Dashboard - Production" sur le Bureau.
) else (
    echo   Des points bloquants subsistent - voir le detail ci-dessus.
    echo   Les corriger, puis relancer :
    echo       scripts\verifier_installation.py
)
echo.
pause
endlocal
exit /b 0
