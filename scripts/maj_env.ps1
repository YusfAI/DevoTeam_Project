# Écrit GOOGLE_SHEET_ID / GOOGLE_SHEET_TAB dans .env, à partir des variables
# d'environnement du même nom.
#
# Appelé par INSTALLER.bat après avoir demandé ces deux valeurs en console
# (set /p) : l'édition du fichier passe par PowerShell plutôt que par du batch
# pur pour rester correcte quel que soit le contenu collé (un lien de feuille
# complet, par exemple) — un remplacement de ligne par ligne, jamais une
# substitution de texte qui interpréterait la valeur comme un motif.
#
# Ne touche à AUCUNE autre ligne du fichier : les commentaires et les autres
# variables (alertes email, Ollama, accès public) restent tels quels.

$ErrorActionPreference = 'Stop'

$Racine = Split-Path -Parent $PSScriptRoot
$FichierEnv = Join-Path $Racine '.env'

if (-not (Test-Path $FichierEnv)) {
    Write-Error "Fichier .env introuvable : $FichierEnv"
    exit 1
}

$valeurs = [ordered]@{
    'GOOGLE_SHEET_ID'  = $env:GOOGLE_SHEET_ID
    'GOOGLE_SHEET_TAB' = $env:GOOGLE_SHEET_TAB
}

$lignes = Get-Content $FichierEnv -Encoding UTF8
$sortie = New-Object System.Collections.Generic.List[string]
$vues = @{}

foreach ($ligne in $lignes) {
    $remplacee = $false
    foreach ($cle in $valeurs.Keys) {
        if ($ligne -match ('^' + [regex]::Escape($cle) + '=')) {
            $sortie.Add("$cle=$($valeurs[$cle])")
            $vues[$cle] = $true
            $remplacee = $true
            break
        }
    }
    if (-not $remplacee) { $sortie.Add($ligne) }
}

# Filet de sécurité : une variable absente du fichier (.env personnalisé,
# ligne supprimée par erreur) est ajoutée plutôt que silencieusement perdue.
foreach ($cle in $valeurs.Keys) {
    if (-not $vues.ContainsKey($cle)) { $sortie.Add("$cle=$($valeurs[$cle])") }
}

# PowerShell 5.1 : "Set-Content -Encoding UTF8" ajoute TOUJOURS un BOM, même
# quand le fichier d'origine n'en a pas (ce qui est le cas de .env, voir
# .env.example) — d'où l'écriture directe via .NET, sans BOM, pour ne pas
# changer l'encodage du fichier à chaque exécution.
$encodageSansBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($FichierEnv, $sortie, $encodageSansBom)
