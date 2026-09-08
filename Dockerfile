# Image d'exécution pour les trois services Docker de l'application : backend,
# et les deux serveurs de tableaux de bord (clair, sombre).
#
# ARCHITECTURE : le code (backend/, scripts/, dac/dashboards, frontend/dist) vit
# EXCLUSIVEMENT dans un montage du dépôt hôte (`.:/app`, voir docker-compose.yml),
# jamais copié dans cette image. Cette image ne fournit QUE le runtime :
# interpréteur Python, dépendances pip, et le moteur de tableaux de bord
# (bruin + dac) avec son pilote DuckDB déjà installé.
#
# Cette séparation n'est pas un choix arbitraire — elle règle un vrai problème :
# `backend/dac_composer.py` écrit chaque dashboard généré par le chat de façon
# atomique (fichier temporaire puis `os.replace()`), et `os.replace()` n'est
# atomique qu'À L'INTÉRIEUR D'UN MÊME SYSTÈME DE FICHIERS. Deux montages Docker
# séparés vers des dossiers pourtant frères sur le même disque échouent en
# EXDEV — vérifié : `st_dev` identique des deux côtés, `os.rename` refuse quand
# même. Un seul montage pour tout `/app` supprime le problème à la racine.
FROM python:3.14-slim-bookworm

# curl + ca-certificates : nécessaires à l'installeur de bruin/dac.
# bash : l'installeur (getbruin.com/install/dac) est écrit pour bash, pas pour
# le "sh" minimal (dash) de Debian — l'invoquer sous dash a échoué en pratique.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates bash git \
    && rm -rf /var/lib/apt/lists/*

# --- Moteur de tableaux de bord (bruin + dac) -------------------------------
RUN bash -c "curl -LsSf https://getbruin.com/install/dac | sh"
ENV PATH="/root/.local/bin:${PATH}"

# --- Dépendances Python ------------------------------------------------------
# AVANT le préchauffage du pilote ci-dessous : celui-ci importe `duckdb` pour
# créer sa base jetable, et a besoin du paquet déjà installé pour ça.
#
# Copiées ici (et seulement ici) plutôt que via le montage : figer les versions
# dans l'IMAGE, pas dans le dossier de travail, est tout l'intérêt de Docker —
# `docker compose build` reproduit exactement le même environnement à chaque
# fois, sur n'importe quelle machine.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- Pilote DuckDB, installé UNE FOIS ici plutôt qu'au premier lancement ----
#
# `bruin` télécharge et extrait le pilote ADBC de DuckDB à sa toute première
# requête. L'application lance des dizaines de requêtes en parallèle dès le
# démarrage (un widget par tableau de bord, sur deux serveurs) : sans ce
# préchauffage, plusieurs processus tentent d'extraire le même fichier en même
# temps et se marchent dessus (constaté sous Windows avec duckdb.dll ; le
# mécanisme est le même ici, seule l'extension change).
#
# Le fichier DuckDB utilisé ici est un JETABLE, hors de /app : le vrai
# ".bruin.yml" et la vraie base arrivent par le montage au démarrage du
# conteneur, bien après la construction de l'image. Seul le CACHE du pilote
# (sous /root, jamais recouvert par le montage) doit survivre jusqu'au runtime.
#
# `git init` jetable : `bruin` (invoqué en sous-main par `dac`) refuse de
# fonctionner s'il ne trouve pas la racine d'un dépôt Git en remontant depuis
# le dossier interrogé — constaté : « failed to find the git repository root »
# sans lui. Au RUNTIME ce sera satisfait naturellement, puisque /app est le
# vrai clone (monté depuis l'hôte, .git compris) ; seule cette étape de
# construction isolée en a besoin artificiellement.
# `cd` explicite plutôt que `--dir` seul : la recherche du dépôt Git par bruin
# part du répertoire de travail DU PROCESSUS, pas de la valeur de `--dir` — un
# `.git` posé dans /opt/warmup ne suffisait pas tant que le process restait
# lancé depuis ailleurs (constaté).
RUN mkdir -p /opt/warmup/data \
    && git init -q /opt/warmup \
    && python -c "\
import duckdb; \
con = duckdb.connect('/opt/warmup/data/warmup.db'); \
con.execute('CREATE TABLE opportunities (id INTEGER)'); \
con.close()" \
    && printf 'default_environment: default\nenvironments:\n    default:\n        connections:\n            duckdb:\n                - name: devoteam_duckdb\n                  path: /opt/warmup/data/warmup.db\n                  read_only: true\n' > /opt/warmup/.bruin.yml \
    && cd /opt/warmup && dac connections \
    && cd / && rm -rf /opt/warmup

WORKDIR /app
