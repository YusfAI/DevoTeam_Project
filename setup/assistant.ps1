# Assistant d'installation — DevoTeam Dashboard
#
# Conduit une installation complète sur un poste neuf, en ne demandant que ce qui
# ne peut pas être deviné : la clé du modèle, la feuille de calcul, et le fichier
# d'identifiants Google.
#
# Il ne réimplémente rien. Les scripts existants font le travail (install.bat,
# verifier_installation.py, test_fonctionnel.py) ; cet assistant les enchaîne et
# s'occupe de ce qu'ils ne savent pas faire : poser les questions, retrouver un
# identifiant dans une URL collée, ouvrir un sélecteur de fichier, et surtout
# attendre que la feuille soit réellement partagée au lieu d'échouer dessus.
#
# Deux règles tenues d'un bout à l'autre :
#   - aucun secret n'est affiché à l'écran ni écrit ailleurs que dans .env ;
#   - chaque étape est rejouable. Relancer l'assistant après une correction
#     reprend là où ça bloquait, sans rien défaire.

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Racine = Split-Path -Parent $PSScriptRoot
$FichierEnv = Join-Path $Racine '.env'
$Modele = Join-Path $Racine '.env.example'
$DossierIdentifiants = Join-Path $Racine 'credentials'
$Identifiants = Join-Path $DossierIdentifiants 'google_service_account.json'
$BruinBin = Join-Path $env:USERPROFILE '.local\bin'

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

function Titre($texte) {
    Write-Host ''
    Write-Host "  $texte" -ForegroundColor Cyan
    Write-Host "  $('-' * $texte.Length)" -ForegroundColor DarkGray
}

function Ok($texte)      { Write-Host "  [OK]    $texte" -ForegroundColor Green }
function Info($texte)    { Write-Host "          $texte" -ForegroundColor Gray }
function Avertir($texte) { Write-Host "  [NOTE]  $texte" -ForegroundColor Yellow }
function Echec($texte)   { Write-Host "  [STOP]  $texte" -ForegroundColor Red }

function Banniere {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host '    DevoTeam Dashboard — assistant d''installation' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  Cet assistant installe tout et ne vous demande que trois choses :' -ForegroundColor White
    Write-Host '    1. la cle Gemini' -ForegroundColor White
    Write-Host '    2. le lien de la feuille Google' -ForegroundColor White
    Write-Host '    3. le fichier JSON du compte de service' -ForegroundColor White
    Write-Host ''
    Write-Host '  Rien de ce que vous saisirez ne sera affiche ni copie ailleurs' -ForegroundColor DarkGray
    Write-Host '  que dans le fichier .env, exclu du depot Git.' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Saisie
# ---------------------------------------------------------------------------

function LireSecret($question, $actuel) {
    # Un secret ne s'affiche pas pendant la frappe. S'il en existe déjà un, une
    # entrée vide le conserve — c'est ce qui rend l'assistant rejouable sans
    # obliger à ressaisir ce qui marchait déjà.
    if ($actuel) {
        Write-Host "  $question" -ForegroundColor White
        Write-Host '          (une valeur existe deja — Entree pour la garder)' -ForegroundColor DarkGray
    } else {
        Write-Host "  $question" -ForegroundColor White
    }
    $secure = Read-Host '        ' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $valeur = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
    if ([string]::IsNullOrWhiteSpace($valeur)) { return $actuel }
    # Google affiche les mots de passe d'application en quatre groupes de quatre.
    # Collés tels quels, les espaces font échouer l'authentification SMTP — cause
    # réelle d'un « Username and Password not accepted » sur un poste de test.
    return $valeur.Trim() -replace '\s', ''
}

function LireTexte($question, $actuel, $defaut) {
    $indice = if ($actuel) { $actuel } elseif ($defaut) { $defaut } else { $null }
    if ($indice) {
        Write-Host "  $question" -ForegroundColor White
        Write-Host "          (Entree = $indice)" -ForegroundColor DarkGray
    } else {
        Write-Host "  $question" -ForegroundColor White
    }
    $valeur = Read-Host '        '
    if ([string]::IsNullOrWhiteSpace($valeur)) { return $indice }
    return $valeur.Trim()
}

function IdentifiantDeFeuille($saisie) {
    # On accepte le lien complet autant que l'identifiant nu : recopier
    # « la partie entre /d/ et /edit » est une manipulation inutile à demander,
    # et c'est une source d'erreur de plus le jour de l'installation.
    if (-not $saisie) { return $null }
    $m = [regex]::Match($saisie, '/d/([A-Za-z0-9_-]{20,})')
    if ($m.Success) { return $m.Groups[1].Value }
    return $saisie.Trim()
}

function ChoisirFichierJson {
    # Un sélecteur graphique plutôt qu'un chemin à taper : le fichier arrive
    # généralement du dossier Téléchargements sous un nom illisible, et le
    # glisser-déposer dans une console n'est pas fiable.
    Add-Type -AssemblyName System.Windows.Forms
    $dialogue = New-Object System.Windows.Forms.OpenFileDialog
    $dialogue.Title = 'Choisir le fichier JSON du compte de service Google'
    $dialogue.Filter = 'Fichiers JSON (*.json)|*.json|Tous les fichiers (*.*)|*.*'
    $dialogue.InitialDirectory = (Join-Path $env:USERPROFILE 'Downloads')
    if ($dialogue.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        return $dialogue.FileName
    }
    return $null
}

# ---------------------------------------------------------------------------
# Lecture / écriture du .env
# ---------------------------------------------------------------------------

function LireEnv {
    $valeurs = @{}
    if (Test-Path $FichierEnv) {
        foreach ($ligne in Get-Content $FichierEnv -Encoding UTF8) {
            if ($ligne -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
                $valeurs[$matches[1]] = $matches[2].Trim()
            }
        }
    }
    return $valeurs
}

function EcrireEnv($valeurs) {
    # Le modèle sert de squelette : on ne réécrit que les valeurs, ce qui préserve
    # les commentaires qui expliquent à quoi sert chaque variable.
    $lignes = if (Test-Path $Modele) { Get-Content $Modele -Encoding UTF8 } else { @() }
    $sortie = New-Object System.Collections.Generic.List[string]
    $vues = @{}

    foreach ($ligne in $lignes) {
        if ($ligne -match '^\s*([A-Z_][A-Z0-9_]*)\s*=') {
            $cle = $matches[1]
            $vues[$cle] = $true
            $val = if ($valeurs.ContainsKey($cle)) { $valeurs[$cle] } else { '' }
            $sortie.Add("$cle=$val")
        } else {
            $sortie.Add($ligne)
        }
    }
    foreach ($cle in $valeurs.Keys) {
        if (-not $vues.ContainsKey($cle)) { $sortie.Add("$cle=$($valeurs[$cle])") }
    }

    Set-Content -Path $FichierEnv -Value $sortie -Encoding UTF8
}

# ---------------------------------------------------------------------------
# 1. Prérequis
# ---------------------------------------------------------------------------

function VerifierPrerequis {
    Titre '1. Prerequis'
    $manque = @()

    foreach ($outil in @(
        @{ Nom = 'python'; Etiquette = 'Python 3.11+'; Lien = 'https://www.python.org/downloads/  (cocher "Add python.exe to PATH")' },
        @{ Nom = 'npm';    Etiquette = 'Node.js LTS';  Lien = 'https://nodejs.org/' }
    )) {
        if (Get-Command $outil.Nom -ErrorAction SilentlyContinue) {
            $version = (& $outil.Nom --version 2>&1 | Select-Object -First 1)
            Ok "$($outil.Etiquette) — $version"
        } else {
            Echec "$($outil.Etiquette) absent"
            Info $outil.Lien
            $manque += $outil.Etiquette
        }
    }

    if ((Test-Path (Join-Path $BruinBin 'dac.exe')) -and (Test-Path (Join-Path $BruinBin 'bruin.exe'))) {
        Ok 'Moteur de tableaux de bord (bruin + dac)'
    } else {
        Avertir 'Moteur de tableaux de bord absent — installation automatique'
        InstallerDac
    }

    if ($manque.Count -gt 0) {
        Write-Host ''
        Echec "Installez d'abord : $($manque -join ', ')  puis relancez cet assistant."
        return $false
    }
    return $true
}

function InstallerDac {
    # L'installeur officiel est un script shell. Git Bash le fournit, et Git est
    # de toute façon nécessaire pour récupérer le projet.
    $bash = @(
        (Join-Path $env:ProgramFiles 'Git\bin\bash.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Git\bin\bash.exe')
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if (-not $bash) {
        Echec 'Git Bash introuvable — necessaire pour installer le moteur.'
        Info 'https://git-scm.com/download/win  puis relancez cet assistant.'
        return
    }

    Info 'Telechargement en cours (une minute environ)...'
    & $bash -lc 'curl -LsSf https://getbruin.com/install/dac | sh' 2>&1 | Out-Null

    if (Test-Path (Join-Path $BruinBin 'dac.exe')) {
        Ok 'Moteur installe'
    } else {
        Echec "L'installation automatique a echoue."
        Info 'Dans Git Bash : curl -LsSf https://getbruin.com/install/dac | sh'
    }
}

# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------

function DemanderConfiguration {
    Titre '2. Configuration'

    $config = LireEnv

    Write-Host ''
    $cle = LireSecret 'Cle Gemini  (aistudio.google.com > Get API key)' $config['GOOGLE_API_KEY']
    if ($cle) { $config['GOOGLE_API_KEY'] = $cle }

    Write-Host ''
    $lien = LireTexte 'Lien OU identifiant de la feuille Google' $config['GOOGLE_SHEET_ID'] $null
    $id = IdentifiantDeFeuille $lien
    if ($id) {
        $config['GOOGLE_SHEET_ID'] = $id
        if ($lien -ne $id) { Info "Identifiant extrait du lien : $id" }
    }

    Write-Host ''
    $onglet = LireTexte "Nom de l'onglet qui contient les donnees" $config['GOOGLE_SHEET_TAB'] 'opportunities'
    if ($onglet) { $config['GOOGLE_SHEET_TAB'] = $onglet }

    if (-not $config['GOOGLE_SHEETS_CREDENTIALS_PATH']) {
        $config['GOOGLE_SHEETS_CREDENTIALS_PATH'] = 'credentials/google_service_account.json'
    }

    Write-Host ''
    Write-Host '  Alertes email quotidiennes — facultatif.' -ForegroundColor White
    Write-Host '  Sans elles, seul le rappel par mail ne part pas.' -ForegroundColor DarkGray
    $reponse = Read-Host '        Configurer maintenant ? (o/N)'
    if ($reponse -match '^[oOyY]') {
        $config['GMAIL_SENDER'] = LireTexte 'Adresse expeditrice' $config['GMAIL_SENDER'] $null
        $config['GMAIL_APP_PASSWORD'] = LireSecret "Mot de passe d'application Gmail (16 caracteres)" $config['GMAIL_APP_PASSWORD']
        $config['ALERT_RECIPIENT_EMAIL'] = LireTexte 'Adresse destinataire' $config['ALERT_RECIPIENT_EMAIL'] $config['GMAIL_SENDER']
    }

    EcrireEnv $config
    Write-Host ''
    Ok '.env ecrit'
}

function DemanderIdentifiants {
    Titre '3. Compte de service Google'

    if (Test-Path $Identifiants) {
        Ok 'Fichier deja en place'
    } else {
        Write-Host '  Selectionnez le fichier JSON telecharge depuis Google Cloud.' -ForegroundColor White
        Info 'Une fenetre de selection va s''ouvrir.'
        $choisi = ChoisirFichierJson
        if (-not $choisi) {
            Echec 'Aucun fichier choisi — la feuille restera inaccessible.'
            return $null
        }
        if (-not (Test-Path $DossierIdentifiants)) {
            New-Item -ItemType Directory -Path $DossierIdentifiants | Out-Null
        }
        Copy-Item $choisi $Identifiants -Force
        Ok 'Fichier copie et renomme correctement'
    }

    try {
        $infos = Get-Content $Identifiants -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Echec 'Le fichier n''est pas un JSON valide.'
        return $null
    }
    if (-not $infos.client_email) {
        Echec 'Ce fichier n''est pas une cle de compte de service.'
        return $null
    }
    return $infos.client_email
}

# ---------------------------------------------------------------------------
# 3. Le partage de la feuille — l'étape qui fait échouer les installations
# ---------------------------------------------------------------------------

function AttendreLePartage($adresse, $python) {
    Titre '4. Partage de la feuille'

    if (-not $adresse) { return $false }

    Write-Host '  La feuille doit etre partagee avec cette adresse, en EDITEUR :' -ForegroundColor White
    Write-Host ''
    Write-Host "      $adresse" -ForegroundColor Yellow
    Write-Host ''
    Info "L'application ecrit dans la feuille — elle y attribue les identifiants"
    Info 'manquants. Un partage en Lecteur laisse tout fonctionner jusqu''au'
    Info 'premier enregistrement, puis echoue sans rien expliquer.'
    Write-Host ''

    $sonde = Join-Path $PSScriptRoot 'sonde_feuille.py'
    for ($essai = 1; $essai -le 10; $essai++) {
        Read-Host '        Partage fait ? Appuyez sur Entree pour verifier'
        $sortie = & $python $sonde 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok 'Feuille accessible en lecture ET en ecriture'
            Info ($sortie | Select-Object -First 1)
            return $true
        }
        Avertir 'Pas encore accessible'
        Info ($sortie | Select-Object -Last 1)
        Write-Host ''
    }
    return $false
}

# ---------------------------------------------------------------------------

function Main {
    Banniere

    if (-not (VerifierPrerequis)) { return 1 }

    DemanderConfiguration
    $adresse = DemanderIdentifiants

    Titre '5. Installation'
    Info 'Environnement Python, dependances, interface — quelques minutes.'
    & (Join-Path $Racine 'scripts\install.bat') | Out-Null

    $python = Join-Path $Racine '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        Echec "L'environnement Python n'a pas ete cree — voir les messages ci-dessus."
        return 1
    }
    Ok 'Installation terminee'

    AttendreLePartage $adresse $python | Out-Null

    Titre '6. Verification'
    & $python (Join-Path $Racine 'scripts\verifier_installation.py')
    $verdict = $LASTEXITCODE

    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    if ($verdict -eq 0) {
        Write-Host '    INSTALLATION TERMINEE' -ForegroundColor Green
        Write-Host ''
        Write-Host '    Lancez l''application par le raccourci du Bureau :' -ForegroundColor White
        Write-Host '      « DevoTeam Dashboard (Production) »' -ForegroundColor White
        Write-Host ''
        Write-Host '    Puis, une fois la page ouverte, verifiez les chiffres :' -ForegroundColor White
        Write-Host '      .venv\Scripts\python.exe scripts\test_fonctionnel.py' -ForegroundColor White
    } else {
        Write-Host '    IL RESTE DES POINTS A CORRIGER' -ForegroundColor Red
        Write-Host ''
        Write-Host '    Corrigez ce qui est signale ci-dessus, puis relancez cet' -ForegroundColor White
        Write-Host '    assistant : il reprendra sans rien defaire.' -ForegroundColor White
    }
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host ''
    return $verdict
}

exit (Main)
