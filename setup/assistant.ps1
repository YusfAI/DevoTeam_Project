# Assistant d'installation — DevoTeam Dashboard
#
# Conduit une installation complète sur un poste neuf, en ne demandant que ce qui
# ne peut pas être deviné : le lien de la feuille de calcul et son onglet. Aucune
# clé API, aucun fichier d'identifiants Google à télécharger ni à sélectionner —
# lecture seule, par le lien d'export public du Sheet. Le modèle (Ollama, local)
# n'a pas de clé à saisir non plus — il est vérifié et installé automatiquement,
# comme le moteur de tableaux de bord (bruin/dac).
#
# Il ne réimplémente rien. Les scripts existants font le travail (install.bat,
# verifier_installation.py, test_fonctionnel.py) ; cet assistant les enchaîne et
# s'occupe de ce qu'ils ne savent pas faire : poser les questions, retrouver un
# identifiant dans une URL collée, et surtout attendre que la feuille soit
# réellement partagée au lieu d'échouer dessus.
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
    Write-Host '  Cet assistant installe tout. Il vous demandera :' -ForegroundColor White
    Write-Host ''
    Write-Host '    1. le lien de la feuille Google              (obligatoire)' -ForegroundColor White
    Write-Host '    2. le nom de l''onglet des donnees            (obligatoire)' -ForegroundColor White
    Write-Host '    3. l''adresse expeditrice des alertes         (facultatif)' -ForegroundColor White
    Write-Host '    4. le mot de passe d''application Gmail       (facultatif)' -ForegroundColor White
    Write-Host '    5. l''adresse destinataire des alertes        (facultatif)' -ForegroundColor White
    Write-Host ''
    Write-Host '  Aucun fichier a telecharger ni a selectionner, aucune cle API :' -ForegroundColor White
    Write-Host '  juste un partage en Lecteur, toute personne disposant du lien.' -ForegroundColor White
    Write-Host ''
    Write-Host '  Rien de ce que vous saisirez ne sera affiche ni copie ailleurs' -ForegroundColor DarkGray
    Write-Host '  que dans le fichier .env, exclu du depot Git.' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Exécution de programmes externes
# ---------------------------------------------------------------------------

function Executer {
    <#
    .SYNOPSIS
      Lance un programme externe sans que PowerShell prenne sa sortie pour une erreur.

    .DESCRIPTION
      PowerShell 5.1 emballe chaque ligne écrite sur la sortie d'erreur d'un
      programme externe dans un ErrorRecord. Avec $ErrorActionPreference = 'Stop',
      un simple message de progression suffit alors à faire avorter le script.

      C'est exactement ce qui s'est produit avec l'installeur du moteur de tableaux
      de bord : « checking GitHub for latest tag », message parfaitement normal,
      interrompait l'assistant alors que l'installation se serait bien terminée.

      La préférence est donc abaissée le temps de l'appel, et le verdict se lit sur
      le CODE DE RETOUR et sur la présence des fichiers attendus — jamais sur le
      flux qu'un programme a choisi pour s'exprimer.
    #>
    param(
        [Parameter(Mandatory)][string] $Programme,
        [string[]] $Arguments = @()
    )

    $precedent = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lignes = & $Programme @Arguments 2>&1 | ForEach-Object { "$_" }
        return [pscustomobject]@{ Code = $LASTEXITCODE; Sortie = $lignes }
    } catch {
        return [pscustomobject]@{ Code = 1; Sortie = @("$_") }
    } finally {
        $ErrorActionPreference = $precedent
    }
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
            $version = (Executer $outil.Nom @('--version')).Sortie | Select-Object -First 1
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

    VerifierOllama

    if ($manque.Count -gt 0) {
        Write-Host ''
        Echec "Installez d'abord : $($manque -join ', ')  puis relancez cet assistant."
        return $false
    }
    return $true
}

function VerifierOllama {
    # Le modele local n'a pas de cle a saisir : il se verifie et s'installe tout
    # seul, comme bruin/dac ci-dessus. OLLAMA_HOST et OLLAMA_MODEL (voir .env.example)
    # restent vides dans l'immense majorite des cas — les valeurs par defaut du code
    # (http://localhost:11434, qwen2.5:7b-instruct-q4_K_M) suffisent.
    $hote = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { 'http://localhost:11434' }
    $modele = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { 'qwen2.5:7b-instruct-q4_K_M' }

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Avertir 'Ollama absent (modele local pour le chat)'
        Info 'https://ollama.com/download  puis relancez cet assistant.'
        return
    }
    Ok 'Ollama installe'

    try {
        Invoke-RestMethod -Uri "$hote/api/tags" -TimeoutSec 5 | Out-Null
        $serviceActif = $true
    } catch {
        $serviceActif = $false
    }
    if (-not $serviceActif) {
        Avertir 'Service Ollama non demarre — demarrage...'
        Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    $liste = Executer 'ollama' @('list')
    if ($liste.Sortie -join "`n" -match [regex]::Escape($modele.Split(':')[0])) {
        Ok "Modele present ($modele)"
        return
    }

    Avertir "Modele absent — telechargement de $modele (plusieurs minutes selon la connexion)"
    $resultat = Executer 'ollama' @('pull', $modele)
    if ($resultat.Code -eq 0) {
        Ok 'Modele telecharge'
    } else {
        Echec "Le telechargement automatique a echoue."
        Info "Manuellement : ollama pull $modele"
    }
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
    $resultat = Executer $bash @('-lc', 'curl -LsSf https://getbruin.com/install/dac | sh')

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
    Write-Host '  Cinq informations. Entree conserve ce qui est deja en place.' -ForegroundColor DarkGray

    $config = LireEnv

    Write-Host ''
    Write-Host '  [1/5] Feuille Google' -ForegroundColor Cyan
    Info "Collez le lien entier depuis le navigateur — l'identifiant en est extrait"
    $lien = LireTexte 'Lien ou identifiant :' $config['GOOGLE_SHEET_ID'] $null
    $id = IdentifiantDeFeuille $lien
    if ($id) {
        $config['GOOGLE_SHEET_ID'] = $id
        if ($lien -ne $id) { Info "Identifiant extrait : $id" }
    }

    Write-Host ''
    Write-Host '  [2/5] Onglet des donnees' -ForegroundColor Cyan
    Info "Le nom de l'onglet, en bas de la feuille, qui contient les opportunites"
    Info "IMPORTANT : doit correspondre EXACTEMENT — un nom incorrect ne produit"
    Info "aucune erreur, il charge silencieusement le premier onglet a la place."
    $onglet = LireTexte 'Nom de l''onglet :' $config['GOOGLE_SHEET_TAB'] 'opportunities'
    if ($onglet) { $config['GOOGLE_SHEET_TAB'] = $onglet }

    # --- Les alertes email ------------------------------------------------
    # Facultatives, mais DEMANDEES. Elles étaient auparavant derrière une question
    # « o/N » dont le défaut valait non : les enterrer ainsi revenait à ne pas les
    # proposer, et personne ne configurait les alertes sans le savoir.
    Write-Host ''
    Write-Host '  ---- Alertes email quotidiennes — facultatif ----' -ForegroundColor DarkGray
    Info 'Un rappel des echeances a 7 jours, envoye chaque matin.'
    Info "Entree a la question suivante pour s'en passer : rien d'autre ne change."

    Write-Host ''
    Write-Host '  [3/5] Adresse expeditrice' -ForegroundColor Cyan
    Info "Le compte Gmail qui ENVOIE le rappel (Entree pour desactiver les alertes)"
    $expediteur = LireTexte 'Adresse expeditrice :' $config['GMAIL_SENDER'] $null

    if ($expediteur) {
        $config['GMAIL_SENDER'] = $expediteur

        Write-Host ''
        Write-Host '  [4/5] Mot de passe d''application Gmail' -ForegroundColor Cyan
        Info 'myaccount.google.com/apppasswords — 16 caracteres.'
        Info "PAS le mot de passe du compte : un mot de passe DEDIE, qui exige"
        Info "que la validation en 2 etapes soit active. Les espaces sont retires."
        $motdepasse = LireSecret 'Collez le mot de passe :' $config['GMAIL_APP_PASSWORD']
        if ($motdepasse) { $config['GMAIL_APP_PASSWORD'] = $motdepasse }

        Write-Host ''
        Write-Host '  [5/5] Adresse destinataire' -ForegroundColor Cyan
        Info 'Qui RECOIT le rappel — la meme adresse convient tres bien.'
        Info 'Plusieurs adresses : separez-les par une virgule.'
        $destinataire = LireTexte 'Adresse destinataire :' $config['ALERT_RECIPIENT_EMAIL'] $expediteur
        if ($destinataire) { $config['ALERT_RECIPIENT_EMAIL'] = $destinataire }
    } else {
        Write-Host ''
        Avertir 'Alertes email desactivees — questions 4 et 5 sans objet.'
        Info "L'application fonctionne integralement ; seul le rappel ne part pas."
        $config['GMAIL_SENDER'] = ''
        $config['GMAIL_APP_PASSWORD'] = ''
        $config['ALERT_RECIPIENT_EMAIL'] = ''
    }

    EcrireEnv $config
    RecapitulerConfiguration $config
}

function RecapitulerConfiguration($config) {
    # Ce que la configuration contient VRAIMENT, avant d'aller plus loin. Une
    # valeur oubliée ne se voit pas dans un .env qu'on ne rouvre jamais ; elle se
    # voit ici, pendant qu'on peut encore la corriger d'un simple relancement.
    Write-Host ''
    Titre 'Recapitulatif'

    $lignes = @(
        @{ Cle = 'GOOGLE_SHEET_ID';       Nom = 'Identifiant de feuille'; Secret = $false; Requis = $true },
        @{ Cle = 'GOOGLE_SHEET_TAB';      Nom = 'Onglet';                 Secret = $false; Requis = $true },
        @{ Cle = 'GMAIL_SENDER';          Nom = 'Alertes — expediteur';   Secret = $false; Requis = $false },
        @{ Cle = 'GMAIL_APP_PASSWORD';    Nom = 'Alertes — mot de passe'; Secret = $true;  Requis = $false },
        @{ Cle = 'ALERT_RECIPIENT_EMAIL'; Nom = 'Alertes — destinataire'; Secret = $false; Requis = $false }
    )

    foreach ($l in $lignes) {
        $valeur = $config[$l.Cle]
        if ($valeur) {
            # Un secret ne se réaffiche jamais : sa longueur suffit à confirmer
            # qu'il a bien été saisi, et ne révèle rien.
            $affiche = if ($l.Secret) { "renseigne ($($valeur.Length) caracteres)" } else { $valeur }
            Ok ("{0,-26} {1}" -f $l.Nom, $affiche)
        } elseif ($l.Requis) {
            Echec ("{0,-26} MANQUANT" -f $l.Nom)
        } else {
            Info ("{0,-26} non configure" -f $l.Nom)
        }
    }

    Write-Host ''
    Info 'DAC_PUBLIC_URL et DAC_DARK_PUBLIC_URL restent vides : elles ne servent'
    Info "qu'a exposer l'application depuis une autre machine (voir la"
    Info 'documentation, section "accessible a distance").'
}

# ---------------------------------------------------------------------------
# 3. Le partage de la feuille — l'étape qui fait échouer les installations
# ---------------------------------------------------------------------------

function AttendreLePartage($python) {
    Titre '3. Partage de la feuille'

    Write-Host '  La feuille doit etre partagee en LECTEUR, a "toute personne' -ForegroundColor White
    Write-Host '  disposant du lien" (bouton Partager > Acces general, en haut a' -ForegroundColor White
    Write-Host '  droite de Google Sheets) :' -ForegroundColor White
    Write-Host ''
    Info "Lecture seule : la cle API ne permet jamais l'ecriture, il n'y a donc"
    Info 'rien de plus a autoriser cote Google.'
    Write-Host ''

    $sonde = Join-Path $PSScriptRoot 'sonde_feuille.py'
    for ($essai = 1; $essai -le 10; $essai++) {
        Read-Host '        Partage fait ? Appuyez sur Entree pour verifier'
        $resultat = Executer $python @($sonde)
        $sortie = $resultat.Sortie
        if ($resultat.Code -eq 0) {
            Ok 'Feuille accessible en lecture'
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

    Titre '4. Installation'
    Info 'Environnement Python, dependances, interface — quelques minutes.'
    $resultat = Executer (Join-Path $Racine 'scripts\install.bat')
    if ($resultat.Code -ne 0) {
        # Non bloquant : install.bat se termine en erreur tant que la
        # configuration est incomplète, ce qui est justement l'état dans
        # lequel l'assistant l'appelle. Le verdict vient du diagnostic.
        Info "L'installation signale des points a corriger — verdict plus bas."
    }

    $python = Join-Path $Racine '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        Echec "L'environnement Python n'a pas ete cree — voir les messages ci-dessus."
        return 1
    }
    Ok 'Installation terminee'

    AttendreLePartage $python | Out-Null

    Titre '5. Verification'
    $resultat = Executer $python @((Join-Path $Racine 'scripts\verifier_installation.py'))
    $resultat.Sortie | ForEach-Object { Write-Host $_ }
    $verdict = $resultat.Code

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
