"""Les deux lanceurs ne font pas le même métier, et cela doit rester vrai.

`start_dev.bat` sert au travail quotidien : rechargement à chaud du backend,
serveur Vite pour le frontend, trois processus. `start_prod.bat` sert à faire
tourner l'application : frontend COMPILÉ et servi par le backend lui-même, pas de
rechargement, deux processus.

La confusion entre les deux est silencieuse et coûteuse. Un `--reload` laissé en
production redémarre le serveur au moindre octet écrit dans le projet — or
l'application écrit elle-même ses tableaux de bord YAML à chaque question, donc
elle se redémarrerait toute seule en boucle. À l'inverse, oublier de compiler le
frontend avant de démarrer sert l'ANCIENNE interface sans le moindre signe que
quelque chose cloche.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DEV = RACINE / "scripts" / "start_dev.bat"
PROD = RACINE / "scripts" / "start_prod.bat"
MAIN_PY = RACINE / "backend" / "main.py"


def _texte(fichier: Path) -> str:
    return fichier.read_text(encoding="utf-8", errors="replace")


def _commandes(fichier: Path) -> str:
    """Le script SANS ses commentaires.

    Ces fichiers s'expliquent longuement, et un `REM ... SANS --reload ...` se
    lisait comme un `--reload` bien réel : le test parlait alors de la prose du
    script au lieu de ce qu'il exécute.
    """
    lignes = [ligne for ligne in _texte(fichier).splitlines()
              if not re.match(r"\s*(?:REM\b|::)", ligne, re.IGNORECASE)]
    return "\n".join(lignes)


def test_les_deux_lanceurs_existent():
    assert DEV.exists() and PROD.exists()


# --- Ce qui distingue la production ---------------------------------------

def test_la_production_ne_recharge_pas_a_chaud():
    """`--reload` surveille l'arborescence — que l'application modifie elle-même.

    Chaque question réécrit `dac/dashboards/_principal.yml` : sous `--reload`, le
    serveur se redémarrerait à chaque réponse qu'il vient de produire.
    """
    assert "--reload" not in _commandes(PROD)


def test_le_developpement_recharge_bien_a_chaud():
    # L'inverse compte tout autant : c'est ce qui rend le lanceur de dev utile.
    assert "--reload" in _commandes(DEV)


def test_la_production_compile_le_frontend_avant_de_demarrer():
    prod = _commandes(PROD)
    position_build = prod.find("npm run build")
    position_uvicorn = prod.find("uvicorn")
    assert position_build != -1, "le frontend n'est jamais compilé"
    assert position_build < position_uvicorn, (
        "le backend démarrerait sur une compilation périmée, et servirait l'ancienne "
        "interface sans le signaler"
    )


def test_une_compilation_ratee_arrete_tout():
    # Servir une interface périmée est pire que ne rien servir : la panne est
    # invisible. Le script doit s'arrêter, pas continuer.
    prod = _commandes(PROD)
    apres_build = prod[prod.find("npm run build"):]
    assert re.search(r"if errorlevel 1", apres_build), "l'échec de compilation n'est pas testé"
    assert "exit /b 1" in apres_build


def test_la_production_ne_lance_pas_le_serveur_de_developpement():
    # Vite ne sert plus à rien en production : le backend sert `frontend/dist`.
    assert "npm run dev" not in _commandes(PROD)


def test_un_seul_worker_en_production():
    """Le jeu de données vit en mémoire dans le processus, et un planificateur y tourne.

    Avec plusieurs workers, chacun garderait sa propre copie des données ET
    relancerait le planificateur : emails d'alerte en double, écritures concurrentes
    dans le Google Sheet.
    """
    prod = _commandes(PROD)
    assert "--workers 1" in prod, "sans ce plafond, uvicorn pourrait être lancé multi-processus"


# --- Le contrat que la production suppose ---------------------------------

def test_le_backend_sait_servir_le_frontend_compile():
    # Tout le mode production tient à cette ligne : sans elle, il n'y a plus rien
    # pour servir l'interface une fois Vite éteint.
    main = _texte(MAIN_PY)
    assert "StaticFiles" in main
    assert "frontend" in main and "dist" in main


@pytest.mark.parametrize("port", ["8000", "8321"])
def test_les_deux_lanceurs_verifient_le_port_avant_de_demarrer(port):
    # Un double-clic alors que l'application tourne laissait l'ancien processus en
    # place : le nouveau ne peut pas prendre le port, et on se retrouve avec un
    # serveur qui répond mais sert du code périmé.
    for lanceur in (DEV, PROD):
        assert re.search(r"is_running %s" % port, _commandes(lanceur)), (
            f"{lanceur.name} ne vérifie pas le port {port}"
        )


def test_les_deux_lanceurs_posent_bruin_dans_le_path():
    """DAC délègue l'exécution du SQL à `bruin`, qu'il cherche dans le PATH.

    Sans cette ligne, DAC démarre normalement, répond 200, et fait échouer chaque
    widget séparément. C'est arrivé, et le message d'erreur ne désigne pas la cause.
    """
    for lanceur in (DEV, PROD):
        texte = _texte(lanceur)
        assert ".local\\bin" in texte, f"{lanceur.name} ne complète pas le PATH"
        assert "bruin.exe" in texte, f"{lanceur.name} ne vérifie pas la présence de bruin"
