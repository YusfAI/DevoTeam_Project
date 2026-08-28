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
$cible = Join-Path $racine 'scripts\start_dev.bat'
$icone = Join-Path $racine 'scripts\devoteam.ico'

if (-not (Test-Path $cible)) {
    throw "Lanceur introuvable : $cible"
}

# OneDrive redirige souvent le Bureau : [Environment]::GetFolderPath suit cette
# redirection, là où un chemin construit à la main sur $env:USERPROFILE la manquerait
# et déposerait le raccourci dans un dossier que personne ne regarde.
$bureau = [Environment]::GetFolderPath('Desktop')
$lien = Join-Path $bureau 'DevoTeam Dashboard.lnk'

$shell = New-Object -ComObject WScript.Shell
$raccourci = $shell.CreateShortcut($lien)
$raccourci.TargetPath = $cible
$raccourci.WorkingDirectory = Join-Path $racine 'scripts'
$raccourci.Description = 'Lance le backend FastAPI, les dashboards Bruin DAC et le frontend Vite, puis ouvre http://localhost:5173'

if (Test-Path $icone) {
    $raccourci.IconLocation = "$icone,0"
}

$raccourci.Save()

Write-Host "Raccourci ecrit : $lien"
Write-Host "  cible  : $cible"
Write-Host "  icone  : $(if (Test-Path $icone) { $icone } else { '(par defaut)' })"
