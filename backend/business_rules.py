"""Règles métier indépendantes de tout moteur d'affichage.

Ces définitions vivaient dans vega_generator.py tant que Vega-Lite produisait les
graphiques. Elles n'ont pourtant rien de spécifique à une bibliothèque : l'ordre du
pipeline commercial et le plafond de lisibilité d'un croisement restent vrais quel
que soit l'outil qui dessine. Les isoler ici a permis de supprimer entièrement le
module Vega sans emporter la logique métier avec lui.
"""

# Ordre du pipeline commercial, du premier contact à la signature. Seules les étapes
# « en cours » en font partie : les sorties (perdu, infructueux, NO GO, hors scope,
# non shortlisté) sont des sorties du pipeline, pas des étapes que chaque
# opportunité traverse — les inclure fausserait aussi bien l'entonnoir que les taux
# de passage calculés dessus (voir sql_builder.funnel_sql).
FUNNEL_STAGE_ORDER = [
    "Lead",
    "Opportunité détectée",
    "En cours de qualification",
    "Complément d'information",
    "En cours de préparation",
    "Propal shortlistée",
    "Manif shortlistée",
    "Manifestation remise",
    "Offre remise",
    "Offre gagnée",
]

# Au-delà, un croisement dimension × practice devient illisible. On garde les N
# valeurs les plus fortes plutôt que de tronquer arbitrairement ou de tout afficher.
MAX_HEATMAP_ROWS = 15


def cap_heatmap_rows(data: list, dimension: str, metric: str,
                      max_n: int = MAX_HEATMAP_ROWS) -> tuple[list, list]:
    """Garde les `max_n` valeurs de `dimension` au total le plus élevé sur `metric`,
    et renvoie aussi cet ordre pour piloter le tri de l'axe.

    Le texte affiché à l'utilisateur réutilise cette même fonction : sans ça, le
    message décrivait plus de lignes que le graphique n'en montrait réellement.
    """
    totals: dict = {}
    for row in data:
        key = row.get(dimension)
        val = row.get(metric) or 0
        totals[key] = totals.get(key, 0) + val

    ordered_keys = [k for k, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:max_n]]
    kept = set(ordered_keys)
    filtered = [row for row in data if row.get(dimension) in kept]
    return filtered, ordered_keys
