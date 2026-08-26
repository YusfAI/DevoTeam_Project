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
    # Confirmé côté métier : la capacité à staffer se vérifie une fois l'offre remise,
    # avant de pouvoir confirmer le gain.
    "En attente du plan de charge",
    "Offre gagnée",
    # La signature est l'étape finale, postérieure au gain : 32 opportunités signées
    # restaient invisibles dans l'entonnoir tant qu'il s'arrêtait à « Offre gagnée »,
    # et le cumul « ayant atteint au moins gagnée » les sous-comptait d'autant.
    "Offre signée",
]

# Opportunités définitivement perdues. Elles sont exclues PAR DÉFAUT de toutes les
# métriques et de tous les graphiques : additionner 66 M€ d'affaires mortes dans un
# « budget total » donnait un chiffre que personne ne peut utiliser pour décider.
#
# Les gagnées et signées restent comptabilisées : ce sont des succès, pas des pertes.
#
# Attention : l'exclusion est un DÉFAUT, pas une censure. Une question portant
# explicitement sur ces statuts (« liste des offres perdues ») doit continuer d'y
# répondre — voir sql_builder._where_clause et db_layer._apply_filters, qui lèvent
# l'exclusion dès que la question filtre elle-même sur le statut.
LOST_STATUSES = [
    "Offre perdue",
    "Infructueux",
    "NO GO",
    "Hors scope",
    "Non shortlisté",
]


# ---------------------------------------------------------------------------
# Offres remises
#
# Le statut décrit l'état COURANT d'une opportunité, pas son historique. Une offre
# partie chez le client et gagnée depuis n'est plus au statut « Offre remise » :
# compter ce seul statut donnait 4 offres là où 57 avaient réellement été déposées.
#
# Sont donc « remises » les opportunités dont le statut ATTESTE le dépôt. La liste a
# été arrêtée avec le métier : les appels d'offres déclarés infructueux et les
# candidatures non shortlistées en sont volontairement absents, leur position exacte
# par rapport à la remise n'étant pas certaine.
# ---------------------------------------------------------------------------

SUBMITTED_STATUSES = [
    "Offre remise",
    "En attente du plan de charge",
    "Offre gagnée",
    "Offre signée",
    "Offre perdue",
]

# Issue d'une offre remise. « En attente » se déduit du reste : déposée, sans
# décision du client à ce jour.
WON_STATUSES = ["Offre gagnée", "Offre signée"]
PENDING_SUBMISSION = ["Offre remise", "En attente du plan de charge"]


# ---------------------------------------------------------------------------
# Affaires chaudes
#
# Une offre déjà partie chez le client, dont la probabilité de gain est au plus
# haut et dont la décision n'est pas encore tombée. C'est le pipeline le plus
# proche de se concrétiser : ce qu'un commercial regarde en premier le lundi matin.
#
# Les statuts retenus sont ceux d'une offre remise ET encore en jeu : une offre
# gagnée ou perdue n'a plus rien de « chaud », sa décision est prise. « En attente
# du plan de charge » en fait partie — l'offre est bien partie chez le client,
# c'est l'étape suivante du pipeline (confirmé avec le métier ; l'inclure fait
# passer le portefeuille chaud de 7 à 14 affaires, et de 3,0 à 7,3 M€).
#
# Cette définition est aussi celle du terme « offre pondérée » employé dans le chat :
# c'est le même concept sous deux noms, et deux définitions divergentes pour une
# même réalité produiraient deux chiffres pour une même question.
# ---------------------------------------------------------------------------

HOT_DEAL_MIN_PROBABILITY = 0.8
HOT_DEAL_STATUSES = list(PENDING_SUBMISSION)

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


# ---------------------------------------------------------------------------
# Choix du type de graphique
#
# Le LLM propose une forme à partir des mots de la question ; ces règles la
# valident ensuite contre la FORME RÉELLE des données. Les deux signaux sont
# complémentaires : « répartition par pays » contient bien le mot qui appelle un
# camembert, mais il y a 21 pays — les angles ne se comparent plus à l'œil et la
# forme demandée dessert la question qu'elle est censée servir.
# ---------------------------------------------------------------------------

# Un camembert reste lisible jusqu'à ~6 parts ; au-delà, comparer deux angles
# voisins devient impossible et le graphique ne se lit plus que par sa légende.
MAX_PIE_SLICES = 6

# Métriques dont les valeurs NE S'ADDITIONNENT PAS : une moyenne de moyennes n'a
# pas de sens statistique. Un camembert les représenterait comme des parts d'un
# tout, alors que leur somme ne veut rien dire.
AVERAGED_METRICS = {"win_probability"}

# Dimensions ordonnées dans le temps : seules elles peuvent porter une courbe.
TEMPORAL_DIMENSIONS = {"deadline_month", "deadline_year"}

# Formes que l'utilisateur demande nommément et qui répondent à un besoin précis
# (une liste, un entonnoir, une corrélation, un croisement). On ne les révise pas :
# les substituer trahirait la question au lieu de l'améliorer.
EXPLICIT_CHART_TYPES = {"table", "funnel", "scatter", "heatmap"}


def distinct_count(dimension: str, filters: dict | None = None,
                    exclude_statuses: list | None = None) -> int | None:
    """Nombre de valeurs distinctes de `dimension` réellement présentes une fois les
    filtres de la question appliqués. Renvoie None si le compte est indéterminable.

    C'est bien la cardinalité APRÈS filtrage qui décide : `country` compte 21 valeurs
    dans le portefeuille entier, mais souvent trois seulement sur un périmètre donné —
    et là, le camembert redevient le bon choix.
    """
    try:
        from .data_store import get_dataframe
        df = get_dataframe()
        if df is None or df.empty or dimension not in df.columns:
            return None

        filters = filters or {}
        for column, value in filters.items():
            if column not in df.columns:
                continue
            if isinstance(value, (list, tuple)):
                df = df[df[column].isin(list(value))]
            else:
                df = df[df[column] == value]

        # Les affaires perdues sont exclues des graphiques (LOST_STATUSES) : les
        # compter ici annoncerait des parts que le camembert n'afficherait jamais.
        excluded = list(exclude_statuses or [])
        if "status" not in filters:
            excluded += [s for s in LOST_STATUSES if s not in excluded]
        if excluded and "status" in df.columns:
            df = df[~df["status"].isin(excluded)]

        return int(df[dimension].nunique())
    except Exception:  # pragma: no cover - dépend de l'état du cache de données
        return None


def choose_chart_type(intent: dict) -> tuple[str, str]:
    """Type de graphique retenu, et la raison SI il diffère de celui demandé.

    La raison n'est pas décorative : elle est affichée sous le graphique. Voir une
    forme différente de celle qu'on a demandée sans explication donne le sentiment
    que l'outil n'a pas compris ; avec l'explication, il apprend quelque chose.
    """
    chart = intent.get("chart_type") or "bar"
    dimension = intent.get("dimension") or ""
    metric = intent.get("metric") or "budget"
    limit = int(intent.get("limit") or 0)

    if chart in EXPLICIT_CHART_TYPES or intent.get("use_raw_table"):
        return chart, ""

    # Sans dimension il n'y a qu'un seul chiffre : aucune forme graphique ne peut le
    # tracer, et un « graphique » à une barre est plus pauvre que le nombre lui-même.
    if not dimension:
        if chart != "kpi_card":
            return "kpi_card", "Un seul chiffre à afficher : le nombre se lit mieux qu'un graphique à une valeur."
        return "kpi_card", ""

    # À l'inverse, un KPI sur une question qui pose un axe d'analyse écraserait en un
    # nombre unique la répartition que l'utilisateur demande précisément à voir.
    if chart == "kpi_card":
        return "bar", ""

    if chart == "pie":
        if metric in AVERAGED_METRICS:
            return "bar", ("Barres plutôt qu'un camembert : une moyenne ne s'additionne pas, "
                            "elle ne forme donc pas des parts d'un tout.")
        if limit > 0:
            return "bar", (f"Barres plutôt qu'un camembert : un top {limit} ne montre pas le tout, "
                            "les parts d'un camembert n'y additionneraient pas 100 %.")
        n = distinct_count(dimension, intent.get("filters"), intent.get("exclude_statuses"))
        if n is not None and n > MAX_PIE_SLICES:
            return "bar", (f"Barres plutôt qu'un camembert : {n} valeurs à comparer, "
                            "au-delà de six parts les angles ne se distinguent plus.")
        return "pie", ""

    if chart in ("line", "area") and dimension not in TEMPORAL_DIMENSIONS:
        return "bar", ("Barres plutôt qu'une courbe : relier des catégories entre elles "
                        "suggérerait une progression qui n'existe pas.")

    # Une dimension temporelle appelle une courbe : des barres côte à côte se comparent
    # deux à deux, là où la question porte sur le mouvement d'ensemble.
    if chart == "bar" and dimension in TEMPORAL_DIMENSIONS:
        return "line", ""

    return chart, ""
