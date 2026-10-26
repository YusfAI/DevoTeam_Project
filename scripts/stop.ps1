# Libère ce que l'application occupe sur le poste, une fois ses conteneurs arrêtés.
#
# Appelé par scripts\stop.bat (raccourci « Arrêter DevoTeam Dashboard »), après
# `docker compose down`. Deux tâches :
#
#   1. Les ports 8000 / 8321 / 8322 / 5173 — occupés par les processus d'une
#      installation NATIVE (start_dev.bat, start_prod.bat), que Docker ne connaît
#      pas. Seuls les processus de l'application sont arrêtés (python, dac, bruin,
#      node) : un autre programme qui occuperait l'un de ces ports est NOMMÉ, jamais
#      tué. Sous Docker, ces ports appartiennent au moteur de Docker Desktop lui-même
#      tant que les conteneurs tournent — l'arrêter casserait Docker, d'où la liste.
#   2. La mémoire du modèle de chat (~5 Go) : déchargée par l'API d'Ollama, qui
#      reste lancé (il ne pèse presque rien sans modèle chargé, et redémarrer
#      l'application ne coûte alors que le rechargement du modèle).
#
# Code de sortie : 0 si les ports de l'application sont libres, 1 sinon.
#
# Messages en ASCII : ils s'affichent dans une fenêtre cmd.exe, qui rend les
# caractères accentués en charabia (voir tests/test_docker.py).

$ErrorActionPreference = 'Continue'

$racine = Split-Path -Parent $PSScriptRoot
$ports = 8000, 8321, 8322, 5173
$processusDeLApplication = 'python', 'pythonw', 'uvicorn', 'dac', 'bruin', 'node'

function Ecoutes {
    @(Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue)
}

# --- 1. Ports ------------------------------------------------------------------
# Plusieurs passes : uvicorn --reload (start_dev.bat) tient le port dans un processus
# parent ET un processus de travail. Arrêter le premier laisse parfois le second à
# l'écoute un instant — on revérifie plutôt que de conclure trop tôt.
$arretes = @()
$etrangers = @{}
for ($passe = 1; $passe -le 3; $passe++) {
    $ecoutes = Ecoutes
    if (-not $ecoutes) { break }
    foreach ($e in ($ecoutes | Sort-Object OwningProcess -Unique)) {
        $p = Get-Process -Id $e.OwningProcess -ErrorAction SilentlyContinue
        if (-not $p) { continue }
        if ($processusDeLApplication -contains $p.ProcessName.ToLower()) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $arretes += "$($p.ProcessName) (port $($e.LocalPort))"
        } else {
            $etrangers[$e.LocalPort] = "$($p.ProcessName) (PID $($p.Id))"
        }
    }
    Start-Sleep -Milliseconds 700
}

# Les fenêtres ouvertes par start_dev.bat / start_prod.bat restent affichées une
# fois leur service arrêté (cmd /k) : on les ferme, elles n'ont plus rien à montrer.
# Repérées par leur titre exact, posé par ces deux lanceurs.
$fenetres = Get-Process cmd -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match '^(Administrat\w*\s*:\s*)?DevoTeam (Backend|DAC|DAC sombre|Frontend)\b'
}
foreach ($f in $fenetres) { Stop-Process -Id $f.Id -Force -ErrorAction SilentlyContinue }

if ($arretes.Count) {
    foreach ($a in ($arretes | Select-Object -Unique)) { Write-Host "        arrete : $a" }
} else {
    Write-Host "        Aucun processus natif de l'application en cours."
}

# --- 2. Mémoire du modèle de chat ----------------------------------------------
# Le modèle et l'adresse d'Ollama sont ceux de .env s'ils y sont renseignés, comme
# pour l'application elle-même (backend/llm.py). Sous Docker, .env peut viser
# host.docker.internal : vu de l'hôte, c'est la boucle locale.
$modele = 'qwen2.5:7b-instruct-q4_K_M'
$hote = 'http://127.0.0.1:11434'
$fichierEnv = Join-Path $racine '.env'
if (Test-Path $fichierEnv) {
    foreach ($ligne in Get-Content $fichierEnv -Encoding UTF8) {
        if ($ligne -match '^\s*OLLAMA_MODEL\s*=\s*"?([^"#\s]+)') { $modele = $Matches[1] }
        if ($ligne -match '^\s*OLLAMA_HOST\s*=\s*"?(https?://[^"#\s]+)' -and $Matches[1] -notmatch 'host\.docker\.internal') {
            $hote = $Matches[1].TrimEnd('/')
        }
    }
}

Write-Host ""
Write-Host "  [3/3] Liberation de la memoire du modele de chat..."
try {
    $enMemoire = Invoke-RestMethod "$hote/api/ps" -TimeoutSec 3
    $charge = @($enMemoire.models | Where-Object { $_.name -eq $modele -or $_.model -eq $modele })
    if (-not $charge) {
        Write-Host "        Le modele n'est pas en memoire : rien a liberer."
    } else {
        # Une requête sans texte avec keep_alive = 0 décharge le modèle : c'est le
        # moyen documenté par Ollama, sans passer par sa ligne de commande — qui,
        # elle, relance l'application Ollama si elle ne tournait pas.
        $corps = @{ model = $modele; keep_alive = 0 } | ConvertTo-Json
        Invoke-RestMethod "$hote/api/generate" -Method Post -ContentType 'application/json' -Body $corps -TimeoutSec 60 | Out-Null
        $go = [math]::Round(($charge[0].size / 1GB), 1)
        Write-Host "        OK - modele decharge, environ $go Go de memoire liberes."
    }
} catch {
    Write-Host "        Ollama ne tourne pas : aucune memoire a liberer."
}

# --- Bilan ---------------------------------------------------------------------
$restants = Ecoutes
if ($restants) {
    Write-Host ""
    foreach ($r in ($restants | Sort-Object LocalPort -Unique)) {
        $qui = $etrangers[$r.LocalPort]
        if (-not $qui) {
            $p = Get-Process -Id $r.OwningProcess -ErrorAction SilentlyContinue
            $qui = if ($p) { "$($p.ProcessName) (PID $($p.Id))" } else { "PID $($r.OwningProcess)" }
        }
        Write-Host "  [ATTENTION] Port $($r.LocalPort) toujours occupe par $qui :"
        if ($qui -match 'docker|wslrelay|vpnkit') {
            # Le moteur de Docker tient le port tant qu'un conteneur l'utilise.
            Write-Host "              des conteneurs tournent encore - voir l'etape [1/3] ci-dessus."
        } else {
            Write-Host "              ce n'est pas un processus de l'application, il n'a pas ete arrete."
        }
    }
    exit 1
}
exit 0
