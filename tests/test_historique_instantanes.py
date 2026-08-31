"""L'historique ne doit jamais proposer une analyse que le backend a effacée.

Deux constantes vivent dans deux langages et deux dossiers, et doivent rester
d'accord : le frontend garde N messages de conversation, le backend garde M
instantanés de tableau de bord. Quand M < N/2, les entrées les plus anciennes de
l'historique ouvrent un fichier supprimé — et DAC répond alors HTTP 200 avec une
coquille de SPA vide, si bien que le frontend ne peut même pas afficher d'erreur :
l'utilisateur clique et regarde un cadre blanc, sans explication.

C'est le genre d'écart qu'aucun des deux côtés ne peut détecter seul.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
COMPOSER_PY = RACINE / "backend" / "dac_composer.py"
HISTORIQUE_JS = RACINE / "frontend" / "src" / "hooks" / "useChatHistory.js"

# Une question consomme deux messages : la demande de l'utilisateur et la réponse.
MESSAGES_PAR_ANALYSE = 2


def _constante(fichier: Path, nom: str) -> int:
    trouve = re.search(rf"^{nom}\s*=\s*(\d+)", fichier.read_text(encoding="utf-8"), re.MULTILINE)
    assert trouve, f"{nom} introuvable dans {fichier.name}"
    return int(trouve.group(1))


def test_le_backend_conserve_autant_d_instantanes_que_l_historique_en_propose():
    max_messages = _constante(HISTORIQUE_JS, "const MAX_MESSAGES")
    max_instantanes = _constante(COMPOSER_PY, "MAX_GENERATED_DASHBOARDS")

    analyses_consultables = max_messages // MESSAGES_PAR_ANALYSE
    assert max_instantanes >= analyses_consultables, (
        f"L'historique propose jusqu'à {analyses_consultables} analyses mais le backend "
        f"n'en conserve que {max_instantanes} : les plus anciennes ouvriraient un "
        f"tableau de bord effacé. Relevez MAX_GENERATED_DASHBOARDS ou abaissez "
        f"MAX_MESSAGES."
    )
