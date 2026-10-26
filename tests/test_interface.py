"""L'interface (Version 3) : icônes Lucide, composants Radix, animations Motion.

Vérifié dans un vrai navigateur avant d'être figé ici, en mode clair et sombre :
icônes à la place des emojis, infobulles au survol, fenêtre « Source de données »
et confirmation d'effacement (Radix), historique qui glisse à l'ouverture comme à
la fermeture. Ces tests gardent ce qui ne se voit pas sur une capture d'écran.
"""
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "frontend" / "src"

# Emojis et symboles graphiques qui tenaient lieu d'icônes (🔗 🩺 🗑️ ☀️ ⚠ ✕ ↗ ← ↻ ⧉ ①…).
# La flèche « → » d'une période (07/01/2025 → 29/12/2026) est de la typographie,
# pas une icône : elle reste permise.
_SYMBOLES = re.compile(
    r"[\U0001F000-\U0001FAFF☀-➿①-⓿⧉▲▼←↗↻]")


def _code_sans_commentaires(texte: str) -> str:
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    return re.sub(r"(^|\s)//.*$", "", texte, flags=re.M)  # commentaires, y compris en fin de ligne


def test_aucun_emoji_ne_sert_d_icone():
    """Un emoji s'affiche différemment d'un Windows à l'autre (couleur, taille,
    parfois un carré vide) ; une icône Lucide est un dessin, identique partout."""
    fautifs = []
    for fichier in SRC.rglob("*.jsx"):
        for ligne in _code_sans_commentaires(fichier.read_text(encoding="utf-8")).splitlines():
            if _SYMBOLES.search(ligne):
                fautifs.append(f"{fichier.name}: {ligne.strip()[:80]}")
    assert not fautifs, fautifs


def test_les_bibliotheques_sont_declarees_et_verrouillees():
    """`npm ci` (service frontend-build) n'installe que ce que le verrou décrit."""
    paquet = json.loads((RACINE / "frontend" / "package.json").read_text(encoding="utf-8"))
    verrou = json.loads((RACINE / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    for nom in ("lucide-react", "motion", "@radix-ui/react-dialog", "@radix-ui/react-tabs",
                "@radix-ui/react-tooltip", "@radix-ui/react-alert-dialog"):
        assert nom in paquet["dependencies"], nom
        assert f"node_modules/{nom}" in verrou["packages"], nom


def test_les_animations_respectent_le_reglage_windows():
    app = (SRC / "App.jsx").read_text(encoding="utf-8")
    css = (SRC / "styles" / "global.css").read_text(encoding="utf-8")
    assert '<MotionConfig reducedMotion="user">' in app
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_la_fenetre_de_donnees_est_un_dialogue_radix():
    """Focus piégé et rendu, Échap, clic extérieur, rôles ARIA : Radix les garantit ;
    la première version les faisait à la main, en partie seulement."""
    panneau = (SRC / "components" / "DataSourcePanel.jsx").read_text(encoding="utf-8")
    assert "<Dialog.Root open={ouvert}" in panneau
    assert "<Tabs.Root value={vue}" in panneau
    assert "addEventListener('keydown'" not in panneau


def test_effacer_la_conversation_demande_confirmation_dans_l_application():
    app = (SRC / "App.jsx").read_text(encoding="utf-8")
    assert "window.confirm" not in app
    assert "<Confirmation" in app


def test_chaque_bouton_icone_porte_un_libelle():
    """Sans libellé, un lecteur d'écran n'annoncerait qu'« bouton »."""
    for fichier in SRC.rglob("*.jsx"):
        for appel in re.findall(r"<BoutonIcone[^>]*>", fichier.read_text(encoding="utf-8")):
            assert 'libelle="' in appel, f"{fichier.name}: {appel}"
