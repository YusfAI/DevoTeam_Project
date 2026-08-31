# Crée (ou met à jour) le raccourci « DevoTeam Dashboard » sur le Bureau.
#
# Un raccourci vit hors du dépôt : sur une machine neuve, ou après un déplacement du
# projet, il n'existe pas ou pointe dans le vide. Ce script le rétablit à partir du
# chemin réel du dépôt, plutôt que de compter sur un artefact créé une fois à la main.
#
#   powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
#
# Le raccourci lance scripts\start_dev.bat, qui démarre le backend FastAPI, les
# dashboards Bruin DAC et le frontend Vite, puis ouvre http://localhost:5173.

$ErrorActionPreference = 'Stop'

$racine = Split-Path -Parent $PSScriptRoot
$icone = Join-Path $racine 'scripts\devoteam.ico'

# DEUX raccourcis, parce que les deux modes ne servent pas au même usage et que se
# tromper est silencieux : le mode développement recharge le backend à chaud et sert
# le frontend par Vite ; le mode production compile le frontend et le fait servir par
# le backend lui-même, sur un seul port. Devant un public, c'est le second qu'on veut
# — un rechargement à chaud au mauvais moment coupe une requête en cours.
$raccourcis = @(
    @{
        Nom = 'DevoTeam Dashboard.lnk'
        Cible = Join-Path $racine 'scripts\start_dev.bat'
        Description = 'Mode developpement : backend rechargé à chaud, frontend Vite, ouvre http://localhost:5173'
    },
    @{
        Nom = 'DevoTeam Dashboard (Production).lnk'
        Cible = Join-Path $racine 'scripts\start_prod.bat'
        Description = 'Mode production : frontend compilé et servi par le backend, ouvre http://127.0.0.1:8000'
    }
)

# OneDrive redirige souvent le Bureau : [Environment]::GetFolderPath suit cette
# redirection, là où un chemin construit à la main sur $env:USERPROFILE la manquerait
# et déposerait le raccourci dans un dossier que personne ne regarde.
$bureau = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

foreach ($r in $raccourcis) {
    if (-not (Test-Path $r.Cible)) {
        throw "Lanceur introuvable : $($r.Cible)"
    }

    $lien = Join-Path $bureau $r.Nom
    $raccourci = $shell.CreateShortcut($lien)
    $raccourci.TargetPath = $r.Cible
    $raccourci.WorkingDirectory = Join-Path $racine 'scripts'
    $raccourci.Description = $r.Description

    if (Test-Path $icone) {
        $raccourci.IconLocation = "$icone,0"
    }

    $raccourci.Save()
    Write-Host "Raccourci ecrit : $lien"
    Write-Host "  cible : $($r.Cible)"
}

Write-Host ""
Write-Host "Icone : $(if (Test-Path $icone) { $icone } else { '(par defaut)' })"
