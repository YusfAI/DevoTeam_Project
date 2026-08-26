"""La palette de graphiques vit dans deux fichiers qui doivent rester identiques.

`frontend/src/styles/tokens.css` sert l'application, `dac/themes/devoteam.yml` sert
les dashboards affichés en iframe. Si les deux divergent, le même pays change de
couleur selon l'endroit où on le regarde — et rien ne le signale.

Le contrôle complet (séparation en vision daltonienne, plancher de chroma, bande de
clarté) se fait avec le validateur de la compétence dataviz, hors dépôt. Ce qui est
vérifié ici est ce qu'on peut vérifier sans lui, et qui couvre les régressions les
plus probables : l'accord entre les deux fichiers, et le contraste avec la surface.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TOKENS = RACINE / "frontend" / "src" / "styles" / "tokens.css"
THEME = RACINE / "dac" / "themes" / "devoteam.yml"

# La surface sur laquelle les marques sont posées, côté clair. Le thème DAC est fixé
# au lancement du serveur et rend toujours en clair : c'est donc la seule surface
# contre laquelle les teintes de graphique doivent être contrastées.
SURFACE_CLAIRE = "#fcfcfb"
CONTRASTE_MINIMUM = 3.0


def _palette_application() -> list:
    """Les huit --series-N du mode clair, c'est-à-dire du premier bloc :root."""
    source = TOKENS.read_text(encoding="utf-8")
    clair = source[: source.index("prefers-color-scheme: dark")]
    return [re.search(r"--series-%d:\s*(#[0-9a-fA-F]{6})" % i, clair).group(1).lower()
            for i in range(1, 9)]


def _palette_dashboards() -> list:
    source = THEME.read_text(encoding="utf-8")
    return [re.search(r'chart-%d:\s*"(#[0-9a-fA-F]{6})"' % i, source).group(1).lower()
            for i in range(1, 9)]


def _luminance(hexa: str) -> float:
    canaux = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lineaire = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
    return 0.2126 * lineaire[0] + 0.7152 * lineaire[1] + 0.0722 * lineaire[2]


def _contraste(a: str, b: str) -> float:
    clair, sombre = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


def test_the_two_files_carry_the_same_palette():
    # Le commentaire du thème le demande depuis toujours ; rien ne le vérifiait.
    assert _palette_application() == _palette_dashboards()


def test_every_hue_is_readable_against_the_chart_surface():
    # Trois teintes passaient sous 3:1 dans la version précédente — le validateur le
    # signalait, mais rien n'empêchait la régression de revenir.
    faibles = [(teinte, round(_contraste(teinte, SURFACE_CLAIRE), 2))
                for teinte in _palette_application()
                if _contraste(teinte, SURFACE_CLAIRE) < CONTRASTE_MINIMUM]
    assert not faibles, "teintes sous %.1f:1 avec la surface : %s" % (CONTRASTE_MINIMUM, faibles)


def test_no_hue_is_used_twice():
    # Deux séries de la même couleur sont indiscernables, quel que soit le reste.
    palette = _palette_application()
    assert len(set(palette)) == len(palette)
