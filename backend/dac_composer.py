"""Compose un dashboard DAC (plusieurs widgets) à partir d'UNE intention validée,
puis l'écrit en YAML dans dac/dashboards/.

Principe : la question de l'utilisateur donne l'angle PRINCIPAL (métrique,
dimension, filtres) via le pipeline existant (llm.py + intent_refiner.py, avec
toute sa validation anti-hallucination) ; ce module l'entoure ensuite de widgets
complémentaires choisis par des RÈGLES DÉTERMINISTES — jamais par le LLM.

Pourquoi des règles plutôt qu'un second appel au LLM : les widgets complémentaires
partagent toujours les mêmes filtres que la question, donc leur pertinence est
déductible sans modèle ; et un appel supplémentaire par question consommerait le
quota gratuit Gemini (~16 requêtes/minute) pour un gain nul en qualité.
"""
import hashlib
import logging
import os
import re
import threading
import time
from pathlib import Path

import yaml

from .business_rules import heatmap_secondary_dimension
from .labels import (
    DEVISE, DIMENSION_LABELS, FILTER_LABELS, METRIC_LABELS, metric_label, with_unit,
)
from .sql_builder import (
    MAX_CATEGORIES, METRIC_SQL, RAW_COLUMNS, _metric_expr, _where_clause, build_sql,
    funnel_sql,
)

logger = logging.getLogger(__name__)


class _LiteralDumper(yaml.SafeDumper):
    """Écrit les chaînes multilignes en bloc littéral (|) plutôt qu'en style quoté.

    Sans ça, PyYAML rend le SQL sous forme 'SELECT ...\\n\\n  FROM ...' : correct
    mais illisible. Or l'intérêt d'un dashboard « as code » est justement d'être
    relu et diffé en revue — le SQL doit rester lisible tel qu'écrit.
    """


def _represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralDumper.add_representer(str, _represent_str)

DASHBOARDS_DIR = Path(__file__).resolve().parent.parent / "dac" / "dashboards"

# Les fichiers provisoires de l'écriture atomique vivent HORS du dossier surveillé
# par DAC. Placés dedans, ils y étaient vus comme des changements : DAC journalisait
# deux lignes par fichier temporaire et par écriture — la moitié de son journal
# n'était plus que ce bruit, ce qui le rendait inutilisable le jour où il fallait y
# lire une vraie panne. Ils y échappaient de surcroît au ménage de
# `_prune_generated`, qui ne connaît que les `_analyse_*.yml`.
#
# Toujours sur le MÊME disque que la destination : `os.replace` n'est atomique qu'à
# l'intérieur d'un système de fichiers, ce qu'un dossier temporaire système ne
# garantit pas.
TEMP_DIR = Path(__file__).resolve().parent.parent / ".dac_tmp"

# Un fichier par question, nommé d'après un condensé de son titre. Un fichier unique
# réécrit à chaque fois était plus simple, mais rendait tout retour en arrière
# impossible : poser une deuxième question effaçait le dashboard de la première,
# alors que l'utilisateur veut souvent comparer ses réponses successives.
GENERATED_PREFIX = "_analyse_"

# Plafond du nombre de dashboards générés conservés : au-delà, les plus anciens sont
# supprimés. Sans ce ménage, chaque question laisserait un fichier derrière elle.
# COUPLÉ à MAX_MESSAGES dans frontend/src/hooks/useChatHistory.js : l'historique y
# conserve 100 messages, soit 50 questions (une question = un message utilisateur +
# une réponse). Garder moins d'instantanés que d'entrées d'historique laissait des
# entrées pointer vers un fichier supprimé — et DAC répond alors 200 avec une page
# vide, donc le frontend ne pouvait même pas le signaler. Les deux nombres doivent
# rester cohérents ; tests/test_historique_instantanes.py le vérifie.
MAX_GENERATED_DASHBOARDS = 50

# Remplacement atomique : nombre de tentatives et pause entre elles. Sous Windows,
# remplacer un fichier qu'un lecteur tient ouvert échoue au lieu d'attendre — et DAC
# relit ces fichiers en permanence. Le lecteur relâche en quelques millisecondes, mais
# le budget est volontairement large (une seconde au total) : au-delà, il n'y a plus
# de repli sûr, et une seconde d'attente dans le pire des cas reste invisible à côté
# du temps de réponse du modèle.
_TENTATIVES_REMPLACEMENT = 40
_ATTENTE_REMPLACEMENT_S = 0.025


def _generated_filename(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{GENERATED_PREFIX}{digest}.yml"


def _prune_generated(keep: str) -> None:
    """Ne garde que les MAX_GENERATED_DASHBOARDS fichiers générés les plus récents.
    `keep` est toujours conservé : c'est celui qu'on vient d'écrire."""
    try:
        fichiers = sorted(
            (f for f in DASHBOARDS_DIR.glob(f"{GENERATED_PREFIX}*.yml")
             if f.name not in (keep, MAIN_FILENAME)),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for vieux in fichiers[MAX_GENERATED_DASHBOARDS - 1:]:
            vieux.unlink()
    except Exception:
        # Le ménage est un confort : son échec ne doit jamais empêcher l'affichage
        # du dashboard qui vient d'être généré.
        logger.warning("Nettoyage des dashboards générés impossible.", exc_info=True)

CONNECTION = "devoteam_duckdb"

# LE dashboard de travail : un seul, toujours au même nom, donc toujours à la même
# URL. Chaque question le RÉÉCRIT plutôt que d'ouvrir un tableau de bord de plus —
# l'utilisateur affine une analyse en place au lieu d'accumuler des onglets qu'il
# faut ensuite retrouver. Le nom est fixe parce que DAC route par nom : le faire
# varier changerait l'URL de l'iframe à chaque question, ce qui est précisément
# l'effet « nouveau dashboard » qu'on cherche à supprimer. La question posée
# s'affiche dans le sous-titre, où DAC rend la description.
MAIN_DASHBOARD_NAME = "Tableau de bord"
MAIN_FILENAME = "_principal.yml"

# Ordre de préférence pour la dimension complémentaire : la plus parlante d'abord.
# On ne prend jamais la dimension déjà affichée, NI une dimension figée par un filtre
# de la question — grouper par practice alors que la question filtre déjà sur une
# seule practice produirait un graphique à une seule barre, sans aucune information.
_COMPLEMENT_PREFERENCE = ["practice", "country", "status", "funding_source", "opp_type", "deadline_month"]


def _complementary_dimension(intent: dict, exclude: set | None = None) -> str:
    """Dimension d'appoint : ni celle déjà affichée, ni une dimension figée par un
    filtre, ni une déjà utilisée par un autre widget du même dashboard (`exclude`) —
    deux graphiques sur le même axe n'apportent rien de plus qu'un seul."""
    primary = intent.get("dimension") or ""
    used = set(exclude or set()) | set((intent.get("filters") or {}).keys()) | {primary}
    for candidate in _COMPLEMENT_PREFERENCE:
        if candidate not in used:
            return candidate
    return ""

_CURRENCY_METRICS = {"budget", "financial_offer", "weighted_amount"}


def _fmt(metric: str) -> str:
    if metric == "win_probability":
        return ".1%"
    return ",.0f"


def _metric_label(metric: str, intent: dict | None = None) -> str:
    """« Budget », ou « Budget moyen » si la question demande une moyenne.

    L'intention est facultative : les widgets de CONTEXTE (part du portefeuille,
    ordre de grandeur) parlent toujours de totaux et ne la passent pas, alors que
    ceux qui affichent la métrique interrogée la passent toujours.
    """
    return metric_label(metric, (intent or {}).get("aggregation", "")).capitalize()


def _dimension_label(dimension: str) -> str:
    return DIMENSION_LABELS.get(dimension, dimension.replace("_", " ")).capitalize()


def _widget_from_intent(intent: dict, title: str, col: int) -> dict:
    """Traduit une intention en widget DAC. Le SQL est produit par sql_builder,
    jamais écrit par le LLM."""
    metric = intent.get("metric") or "budget"
    dimension = intent.get("dimension") or ""
    chart_type = intent.get("chart_type") or "bar"
    sql = build_sql(intent)
    fmt = _fmt(metric)

    if chart_type == "kpi_card" or (not dimension and chart_type not in ("scatter", "table", "funnel")):
        return {
            "name": title, "type": "metric", "col": col, "sql": sql,
            "value": {"field": "value", "type": "number", "format": fmt},
        }

    if chart_type == "table" or intent.get("use_raw_table"):
        labels = {
            "buyer": "Client", "country": "Pays", "practice": "Practice",
            "status": "Statut", "deadline": "Échéance",
            "days_remaining": "Jours restants", "budget": "Budget (%s)" % DEVISE,
            "win_probability": "Probabilité",
        }
        columns = []
        for name in RAW_COLUMNS:
            column = {"name": name, "label": labels.get(name, name)}
            if name in ("budget", "days_remaining"):
                # Pas `currency` pour le budget : ce format applique le préfixe `$`
                # du formateur d3 de DAC, soit des dollars affichés là où il s'agit
                # de dinars. L'unité est portée par le libellé de la colonne.
                column["number"] = "number"
            columns.append(column)
        return {"name": title, "type": "table", "col": col, "sql": sql, "columns": columns}

    if chart_type == "funnel":
        return {
            "name": title, "type": "chart", "chart": "funnel", "col": col, "sql": sql,
            "label": "status", "value": {"field": metric},
        }

    if chart_type == "pie":
        return {
            "name": title, "type": "chart", "chart": "pie", "col": col, "sql": sql,
            "label": dimension, "value": {"field": metric},
        }

    if chart_type == "scatter":
        return {
            "name": title, "type": "chart", "chart": "scatter", "col": col, "sql": sql,
            "x": {"field": "budget", "type": "number", "title": "Budget"},
            "y": {"field": "win_probability", "type": "number", "title": "Probabilité de gain"},
        }

    if chart_type == "heatmap":
        secondary = heatmap_secondary_dimension(dimension)
        return {
            "name": title, "type": "chart", "chart": "heatmap", "col": col, "sql": sql,
            "x": {"field": secondary, "type": "category", "title": _dimension_label(secondary)},
            "y": {"field": dimension, "type": "category", "title": _dimension_label(dimension)},
            "value": {"field": metric},
        }

    # bar / line / area : même structure x/y, seul le type de tracé change.
    chart = chart_type if chart_type in ("bar", "line", "area") else "bar"
    widget = {
        "name": title, "type": "chart", "chart": chart, "col": col, "sql": sql,
        "x": {"field": dimension, "type": "category", "title": _dimension_label(dimension)},
        "y": {"field": metric, "type": "number",
               "title": with_unit(_metric_label(metric, intent), metric), "format": fmt},
    }
    if chart == "bar" and dimension:
        # Une couleur par catégorie plutôt qu'une teinte unique pour toutes les
        # barres : chaque valeur se distingue immédiatement et garde la même couleur
        # que dans les autres graphiques du dashboard.
        #
        # Réservé aux barres : sur une courbe ou une aire, colorer par catégorie
        # découperait la série en segments isolés et détruirait la tendance, qui est
        # justement ce que ces formes servent à montrer.
        widget["color"] = {"field": dimension}
    return widget


# Ce qui définit le PÉRIMÈTRE et le MODE DE CALCUL d'une question : tout widget
# dérivé doit en hériter intégralement, sinon le tableau de bord juxtapose des
# chiffres qui ne parlent pas de la même chose.
#
# Cette liste était écrite en dur, deux fois, et n'avait pas suivi l'ajout de
# `exclude_filters` ni celui de `aggregation`. Conséquences constatées : sur
# « budget par pays hors Tunisie », cinq widgets sur huit incluaient la Tunisie à
# côté d'un graphique qui l'excluait ; et sur « budget moyen par client », deux
# widgets affichaient « Budget moyen » au-dessus d'une SOMME — le libellé venait de
# l'intention d'origine, le calcul d'une copie amputée.
#
# `tests/test_dac_composer.py` vérifie que tout widget composé porte bien chacune de
# ces clés : ajouter un champ de périmètre sans l'inscrire ici fait échouer les tests.
_CLES_DE_PERIMETRE = (
    "filters", "range_filters", "exclude_statuses", "exclude_filters", "aggregation",
    "hot_deals",
)


def _perimetre(intent: dict) -> dict:
    """Les clés de périmètre de `intent`, telles quelles."""
    return {cle: intent[cle] for cle in _CLES_DE_PERIMETRE if intent.get(cle)}


def _kpi_intent(intent: dict, metric: str) -> dict:
    """Même périmètre que la question, mais sans dimension : un total global."""
    return {
        "metric": metric, "dimension": "", "chart_type": "kpi_card",
        "filters": {}, "range_filters": {}, "exclude_statuses": [],
        "use_raw_table": False, "limit": 0,
        **_perimetre(intent),
    }


def _variant_intent(intent: dict, **overrides) -> dict:
    """Copie de l'intention en ne changeant que ce qui est demandé — les filtres
    de la question sont TOUJOURS conservés, pour que tous les widgets du dashboard
    parlent bien du même périmètre."""
    variant = {
        "metric": intent.get("metric") or "budget",
        "dimension": intent.get("dimension") or "",
        "chart_type": intent.get("chart_type") or "bar",
        "filters": {}, "range_filters": {}, "exclude_statuses": [],
        "use_raw_table": intent.get("use_raw_table", False),
        "limit": intent.get("limit") or 0,
        # Le périmètre en dernier : il fait autorité sur les valeurs par défaut
        # ci-dessus, et un seul endroit décide de ce qu'il contient.
        **_perimetre(intent),
    }
    variant.update(overrides)
    return variant


def compose_widgets(intent: dict) -> list:
    """Compose le dashboard en fonction du TYPE de question posée.

    Une question temporelle, une question de répartition et une question de pipeline
    n'appellent pas les mêmes widgets : servir le même squelette à toutes revenait à
    afficher un entonnoir de vente sous une courbe d'évolution, où il ne répondait à
    rien. Chaque archétype a donc sa propre composition, mais tous les widgets
    conservent les filtres de la question — sinon le dashboard mélangerait des
    chiffres qui ne se comparent pas."""
    archetype = _question_archetype(intent)
    if archetype == "comparison":
        return _compose_comparison(intent)
    if archetype == "temporal":
        return _compose_temporal(intent)
    if archetype == "pipeline":
        return _compose_pipeline(intent)
    if archetype == "detail":
        return _compose_detail(intent)
    if archetype == "correlation":
        return _compose_correlation(intent)
    return _compose_breakdown(intent)


def _compared_values(intent: dict):
    """Colonne et valeurs mises en regard quand la question compare explicitement
    (« compare la France et le Maroc » → filters={'country': ['France','Maroc']})."""
    for column, value in (intent.get("filters") or {}).items():
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return column, list(value)
    return None, []


def _question_archetype(intent: dict) -> str:
    chart_type = intent.get("chart_type") or "bar"
    dimension = intent.get("dimension") or ""
    if chart_type == "scatter":
        return "correlation"
    if chart_type == "funnel" or dimension == "status":
        return "pipeline"
    if chart_type == "table" or intent.get("use_raw_table"):
        return "detail"
    # Une comparaison prime sur les autres formes : la question porte sur l'ÉCART
    # entre plusieurs entités, pas sur la répartition de chacune prise isolément.
    if _compared_values(intent)[0]:
        return "comparison"
    if dimension in ("deadline_month", "deadline_year"):
        return "temporal"
    return "breakdown"


def _kpi_row(intent: dict, metric: str) -> list:
    """Les chiffres du périmètre, chacun accompagné de quoi le situer.

    Un total seul ne veut rien dire : on ajoute donc systématiquement un point de
    comparaison — le poids du périmètre dans le portefeuille quand la question
    filtre, sinon la valeur moyenne par opportunité."""
    widgets = [_widget_from_intent(_kpi_intent(intent, metric),
                                    with_unit(_metric_label(metric, intent), metric), col=3)]
    if metric != "nb_opportunities":
        widgets.append(_widget_from_intent(
            _kpi_intent(intent, "nb_opportunities"), "Opportunités", col=3))

    # Contexte : « part du portefeuille » n'a de sens que si un filtre restreint le
    # périmètre (sans filtre elle vaudrait toujours 100 %) — sinon on donne l'ordre
    # de grandeur unitaire, qui situe le total tout aussi bien.
    if intent.get("filters") or intent.get("range_filters"):
        widgets.append(_share_of_portfolio_widget(intent, metric, col=3))
    elif metric != "nb_opportunities" and intent.get("aggregation") != "avg":
        # Pas de moyenne d'appoint quand la question EST déjà une moyenne : le KPI
        # principal l'affiche alors, et les deux widgets portaient le même nom
        # (« Budget moyen (DT) ») pour le même chiffre, côte à côte.
        widgets.append(_average_widget(intent, metric, col=3))

    if metric != "weighted_amount":
        widget = _widget_from_intent(
            _kpi_intent(intent, "weighted_amount"), "Montant pondéré (%s)" % DEVISE, col=3)
        # Mention explicite : weighted_amount est vide pour ~49 % des opportunités
        # (probabilité de gain non renseignée). Sans cette précision, le chiffre se
        # lit comme un total du portefeuille alors qu'il n'en couvre que la moitié.
        widget["description"] = (
            "Somme des seules opportunités dont la probabilité de gain est renseignée "
            "— environ la moitié du portefeuille."
        )
        widgets.append(widget)

    # Les KPI occupent la ligne entière, répartis à parts égales. Avec une largeur
    # fixe, deux KPI n'en remplissaient que la moitié : le graphique suivant venait
    # se glisser à côté d'eux, écrasé sur une hauteur de tuile de chiffre.
    largeur = 12 // len(widgets)
    for w in widgets:
        w["col"] = largeur
    return widgets


def _primary(intent: dict, col: int) -> dict:
    widget = _widget_from_intent(intent, intent.get("goal") or "Résultat", col=col)
    # Quand la forme retenue diffère de celle demandée, la raison s'affiche sous le
    # graphique : voir des barres après avoir demandé un camembert, sans explication,
    # donne le sentiment que l'outil n'a pas compris la question.
    raison = intent.get("chart_type_reason")
    if raison and "description" not in widget:
        widget["description"] = raison
    return widget


def _complement_widget(intent: dict, metric: str, col: int, exclude: set | None = None):
    """Le même chiffre sur une autre dimension. Le type de graphique découle de la
    cardinalité RÉELLE de cette dimension, pas d'un choix fixe : un camembert de
    16 parts (le nombre de statuts) est illisible."""
    complement = _complementary_dimension(intent, exclude=exclude)
    if not complement:
        return None
    chart = "pie" if _is_pie_readable(complement, intent) else "bar"
    widget = _widget_from_intent(
        _variant_intent(intent, dimension=complement, chart_type=chart,
                         use_raw_table=False, limit=0),
        f"{_metric_label(metric, intent)} par {_dimension_label(complement).lower()}",
        col=col,
    )
    widget["_dimension"] = complement  # retiré avant écriture, sert au chaînage
    return widget


def _detail_widget(intent: dict, col: int = 12) -> dict:
    return _widget_from_intent(
        _variant_intent(intent, chart_type="table", use_raw_table=True, limit=0),
        "Détail des opportunités", col=col)


# Un camembert reste lisible jusqu'à ~6 parts ; au-delà les angles ne se comparent
# plus à l'œil. C'est la cardinalité réelle des données filtrées qui décide, pas une
# préférence figée — status compte 16 valeurs, country 21.
MAX_PIE_SLICES = 6


def _is_pie_readable(dimension: str, intent: dict) -> bool:
    """Compte les valeurs distinctes réellement présentes APRÈS application des
    filtres de la question — une dimension à forte cardinalité peut n'en avoir que
    trois une fois le périmètre restreint."""
    try:
        from .data_store import get_dataframe
        df = get_dataframe()
        if df is None or df.empty or dimension not in df.columns:
            return False
        for column, value in (intent.get("filters") or {}).items():
            if column not in df.columns:
                continue
            if isinstance(value, (list, tuple)):
                df = df[df[column].isin(list(value))]
            else:
                df = df[df[column] == value]
        return 0 < df[dimension].nunique() <= MAX_PIE_SLICES
    except Exception:
        logger.warning("Cardinalité de %s indéterminable, repli sur un graphique en barres.",
                        dimension, exc_info=True)
        return False


def _share_of_portfolio_widget(intent: dict, metric: str, col: int) -> dict:
    """Poids du périmètre interrogé dans le portefeuille entier.

    C'est la réponse directe à « 72 MDT, c'est beaucoup ? » : un montant absolu n'a
    aucun point de comparaison tant qu'on ne sait pas ce qu'il représente du tout.
    Ne vaut la peine que si la question filtre — sans filtre, la part vaut 100 %.

    Reste sur une SOMME même quand la question demande une moyenne : une part se
    calcule sur des totaux, et un rapport de deux moyennes ne représenterait aucune
    part de quoi que ce soit. Le libellé du widget dit bien « part du portefeuille »,
    pas « part de la moyenne »."""
    expr = METRIC_SQL.get(metric, METRIC_SQL["budget"])
    where = _where_clause(intent)
    sql = (
        f"SELECT (SELECT {expr} FROM opportunities WHERE {where})\n"
        f"     / NULLIF((SELECT {expr} FROM opportunities), 0) AS value"
    )
    return {
        "name": "Part du portefeuille", "type": "metric", "col": col, "sql": sql,
        "description": f"Ce que représente ce périmètre sur l'ensemble ({_metric_label(metric).lower()}).",
        "value": {"field": "value", "type": "number", "format": ".1%"},
    }


def _average_widget(intent: dict, metric: str, col: int) -> dict:
    """Valeur moyenne par opportunité : un ordre de grandeur unitaire, qui situe le
    total (350 opportunités à 470 kDT n'est pas la même histoire que 10 à 16 MDT)."""
    column = {"budget": "budget", "financial_offer": "financial_offer",
              "weighted_amount": "weighted_amount"}.get(metric, "budget")
    where = _where_clause(intent)
    return {
        "name": with_unit(f"{_metric_label(metric)} moyen", metric), "type": "metric", "col": col,
        "sql": f"SELECT AVG({column}) AS value\nFROM opportunities\nWHERE {where}",
        "description": "Moyenne par opportunité du périmètre.",
        "value": {"field": "value", "type": "number", "format": ",.0f"},
    }


def _share_of_total_widget(intent: dict, metric: str, col: int) -> dict:
    """Part de chaque valeur dans le total, en pourcentage. Répond à « 72 MDT,
    c'est beaucoup ? » : un chiffre absolu seul n'a pas de point de comparaison.

    Sur des sommes, comme `_share_of_portfolio_widget` et pour la même raison : une
    part se calcule sur des totaux, jamais sur des moyennes."""
    dimension = intent.get("dimension") or "practice"
    expr = METRIC_SQL.get(metric, METRIC_SQL["budget"])
    where = _where_clause(intent)
    sql = (
        f"WITH agg AS (\n"
        f"  SELECT {dimension} AS dim, {expr} AS val\n"
        f"  FROM opportunities\n  WHERE {where}\n  GROUP BY {dimension}\n"
        f")\n"
        f"SELECT dim AS {dimension}, val / SUM(val) OVER () AS part\n"
        f"FROM agg\nORDER BY part DESC\nLIMIT {MAX_CATEGORIES}"
    )
    return {
        "name": f"Part du total par {_dimension_label(dimension).lower()}",
        "type": "chart", "chart": "bar", "col": col, "sql": sql,
        "x": {"field": dimension, "type": "category", "title": _dimension_label(dimension)},
        "y": {"field": "part", "type": "number", "title": "Part du total", "format": ".1%"},
        # Même code couleur que le graphique principal, qui porte la même dimension :
        # l'œil relie les deux lectures d'une catégorie sans relire les étiquettes.
        "color": {"field": dimension},
    }


def _conversion_widget(intent: dict, col: int) -> dict:
    """Taux de passage d'une étape du pipeline à la suivante.

    L'entonnoir montre des volumes ; il ne dit pas OÙ ça coince. Le taux de passage
    répond directement à « où perd-on les deals ? » — la question métier réelle
    derrière une demande de pipeline. Le calcul repose sur les cumuls « ayant atteint
    au moins cette étape » (voir sql_builder.funnel_sql) : rapporter deux comptages
    d'états courants donnerait des taux au-delà de 100 %, dépourvus de sens."""
    return {
        "name": "Taux de passage entre étapes",
        "type": "chart", "chart": "bar", "col": col,
        "sql": funnel_sql(intent, conversion=True),
        "description": "Part des opportunités ayant atteint une étape qui franchissent la suivante.",
        "x": {"field": "status", "type": "category", "title": "Étape"},
        "y": {"field": "taux", "type": "number", "title": "Taux de passage", "format": ".0%"},
        # Une couleur par étape, identique à celle de l'entonnoir affiché à côté :
        # les deux graphiques parlent des mêmes étapes, ils doivent les peindre pareil.
        "color": {"field": "status"},
    }


def _compose_breakdown(intent: dict) -> list:
    """« budget par pays » : la répartition, plus un second axe de lecture."""
    metric = intent.get("metric") or "budget"
    widgets = _kpi_row(intent, metric)
    # Moitiés égales plutôt que 7/5 : quand le complément est un camembert, DAC
    # affiche « nom NN% » à côté de chaque part et ces étiquettes sont tronquées
    # dans une colonne étroite.
    widgets.append(_primary(intent, col=6))
    complement = _complement_widget(intent, metric, col=6)
    if complement:
        widgets.append(complement)
    widgets.append(_share_of_total_widget(intent, metric, col=6))
    widgets.append(_detail_widget(intent, col=6))
    return widgets


def _compose_temporal(intent: dict) -> list:
    """« évolution du budget par mois » : la tendance et ce qui la compose — pas
    d'entonnoir, qui ne dit rien d'une évolution dans le temps."""
    metric = intent.get("metric") or "budget"
    widgets = _kpi_row(intent, metric)
    widgets.append(_primary(intent, col=12))
    complement = _complement_widget(intent, metric, col=6)
    if complement:
        widgets.append(complement)
    widgets.append(_detail_widget(intent, col=6 if complement else 12))
    return widgets


def _compose_pipeline(intent: dict) -> list:
    """« entonnoir de vente » : les volumes par étape ET le taux de passage entre
    elles — c'est le taux qui répond à « où perd-on les deals ? », pas le volume."""
    metric = intent.get("metric") or "nb_opportunities"
    funnel_intent = _variant_intent(intent, metric="nb_opportunities", dimension="status",
                                     chart_type="funnel", use_raw_table=False, limit=0)
    widgets = _kpi_row(intent, metric)
    widgets.append(_widget_from_intent(funnel_intent, "Entonnoir de vente", col=6))
    widgets.append(_conversion_widget(intent, col=6))
    widgets.append(_widget_from_intent(
        _variant_intent(intent, metric="budget", dimension="status",
                         chart_type="bar", use_raw_table=False, limit=0),
        "Budget engagé par étape", col=6))
    widgets.append(_detail_widget(intent, col=6))
    return widgets


def _compose_detail(intent: dict) -> list:
    """« liste des opportunités urgentes » : la liste d'abord, puis deux angles de
    lecture DIFFÉRENTS pour situer ce que contient cette liste."""
    metric = intent.get("metric") or "budget"
    widgets = _kpi_row(intent, metric)
    widgets.append(_primary(intent, col=12))

    first = _complement_widget(intent, metric, col=6)
    if first:
        widgets.append(first)
        # Second axe explicitement différent du premier : sans cette exclusion, les
        # deux widgets retombaient tous deux sur « practice » et disaient la même chose.
        second = _complement_widget(intent, metric, col=6, exclude={first["_dimension"]})
        if second:
            widgets.append(second)
        else:
            widgets[-1]["col"] = 12
    return widgets


def _grouped_bar_widget(intent: dict, metric: str, axis: str, series: str, col: int) -> dict:
    """Barres groupées : `axis` en abscisse, une couleur par valeur de `series`.

    C'est ce qui rend une comparaison lisible — voir côte à côte le budget de chaque
    pays DÉCOMPOSÉ par practice montre d'où vient l'écart, là où deux barres totales
    disent seulement qu'il existe."""
    expr = _metric_expr(metric, intent)
    where = _where_clause(intent)
    sql = (
        f"SELECT {axis}, {series}, {expr} AS {metric}\n"
        f"FROM opportunities\nWHERE {where}\n"
        f"GROUP BY {axis}, {series}\n"
        f"ORDER BY {axis}, {series}"
    )
    return {
        "name": f"{_metric_label(metric, intent)} par {_dimension_label(axis).lower()} "
                 f"et {_dimension_label(series).lower()}",
        "type": "chart", "chart": "bar", "col": col, "sql": sql, "stacked": True,
        "color": {"field": series},
        "x": {"field": axis, "type": "category", "title": _dimension_label(axis)},
        "y": {"field": metric, "type": "number",
               "title": with_unit(_metric_label(metric, intent), metric), "format": _fmt(metric)},
    }


def _compose_comparison(intent: dict) -> list:
    """« compare la France et le Maroc » : montrer l'écart, puis l'expliquer.

    Une comparaison ne se satisfait pas de deux barres : il faut la part relative de
    chacun (l'écart en proportion, pas seulement en valeur) et une décomposition qui
    montre D'OÙ vient cet écart."""
    metric = intent.get("metric") or "budget"
    column, values = _compared_values(intent)
    widgets = _kpi_row(intent, metric)

    compare_intent = _variant_intent(intent, dimension=column, chart_type="bar",
                                      use_raw_table=False, limit=0)
    widgets.append(_widget_from_intent(
        compare_intent, intent.get("goal") or f"Comparaison par {_dimension_label(column).lower()}",
        col=6))

    # Part de chacun dans le total comparé : dit si l'écart est marginal ou massif.
    widgets.append(_share_of_total_widget(compare_intent, metric, col=6))

    # D'où vient l'écart : même comparaison, décomposée par une seconde dimension.
    series = _complementary_dimension(intent, exclude={column})
    if series:
        widgets.append(_grouped_bar_widget(intent, metric, axis=column, series=series, col=12))

    widgets.append(_detail_widget(intent, col=12))
    return widgets


def _compose_correlation(intent: dict) -> list:
    """« lien entre budget et probabilité de gain » : le nuage, plus les deux
    distributions qui expliquent sa forme."""
    metric = intent.get("metric") or "budget"
    widgets = _kpi_row(intent, metric)
    widgets.append(_primary(intent, col=12))
    widgets.append(_widget_from_intent(
        _variant_intent(intent, metric="win_probability", dimension="practice",
                         chart_type="bar", use_raw_table=False, limit=0),
        "Probabilité de gain moyenne par practice", col=6))
    widgets.append(_detail_widget(intent, col=6))
    return widgets


def _pack_rows(widgets: list) -> list:
    """Répartit les widgets en lignes de 12 colonnes (la grille DAC)."""
    # Les clés internes (préfixées par « _ ») servent uniquement à la composition et
    # n'appartiennent pas au schéma DAC : les laisser ferait échouer `dac validate`.
    widgets = [{k: v for k, v in w.items() if not k.startswith("_")} for w in widgets]
    rows, current, used = [], [], 0
    for widget in widgets:
        col = widget.get("col", 6)
        if used + col > 12 and current:
            rows.append({"widgets": current})
            current, used = [], 0
        current.append(widget)
        used += col
    if current:
        rows.append({"widgets": current})

    # Une ligne incomplète laisse une bande vide au milieu du dashboard : le dernier
    # widget d'une composition impaire s'affichait sur une demi-largeur, sans rien à
    # côté. On répartit la place restante entre les widgets de la ligne.
    for row in rows:
        occupe = sum(w.get("col", 6) for w in row["widgets"])
        if occupe < 12:
            largeur = 12 // len(row["widgets"])
            for w in row["widgets"]:
                w["col"] = largeur
            row["widgets"][0]["col"] += 12 - largeur * len(row["widgets"])
    return rows


def _borne_lisible(colonne: str, regle: dict) -> str:
    """« probabilité de gain 80 % et plus » plutôt que « win_probability >= 0.8 ».

    Un titre de tableau de bord est lu par quelqu'un qui ne connaît pas les noms de
    colonnes ; y laisser l'opérateur brut le rendait illisible.
    """
    libelle = FILTER_LABELS.get(colonne, colonne.replace("_", " "))
    op = regle.get("op", "")
    valeur = regle.get("value", "")

    if colonne == "win_probability":
        try:
            valeur = "%g %%" % (float(valeur) * 100)
        except (TypeError, ValueError):
            pass

    if op == "between" and isinstance(valeur, (list, tuple)) and len(valeur) == 2:
        return "%s de %s à %s" % (libelle, valeur[0], valeur[1])
    mots = {">=": "et plus", ">": "et plus", "<=": "au plus", "<": "au plus", "=": ""}
    return ("%s %s %s" % (libelle, valeur, mots.get(op, op))).strip()


def _titre_depuis_intention(intent: dict) -> str:
    """« Budget moyen par pays — practice = Risk Advisory », construit de toutes pièces.

    Chaque morceau vient d'une valeur déjà validée contre la whitelist : la métrique,
    l'axe et les filtres résolus. Rien de ce que l'utilisateur a tapé n'y transite,
    donc le nom du tableau de bord reste un nom de tableau de bord.
    """
    metric = intent.get("metric") or ""
    if not metric or intent.get("is_conversation"):
        return ""

    titre = _metric_label(metric, intent)
    dimension = intent.get("dimension") or ""
    if dimension:
        titre += " par %s" % _dimension_label(dimension).lower()

    # Les filtres appliqués font partie de l'identité de l'analyse : sans eux,
    # « budget par pays » et « budget par pays pour Risk Advisory » porteraient le
    # même nom et se partageraient donc le même instantané.
    precisions = []
    for cle, valeur in (intent.get("filters") or {}).items():
        libelle = FILTER_LABELS.get(cle, cle)
        if isinstance(valeur, (list, tuple)):
            precisions.append("%s %s" % (libelle, ", ".join(str(v) for v in valeur)))
        else:
            precisions.append("%s %s" % (libelle, valeur))
    for cle, regle in (intent.get("range_filters") or {}).items():
        precisions.append(_borne_lisible(cle, regle))
    if precisions:
        # Tiret simple, pas cadratin : le nom sert aussi de route DAC, et
        # `_dashboard_name` ne garde que les caractères sûrs pour une URL.
        titre += " - %s" % " et ".join(precisions)
    return titre


def _analysis_title(query: str, intent: dict) -> str:
    """Intitulé de l'analyse : l'objectif résolu de préférence à la phrase tapée.

    Une retouche ne se décrit pas elle-même — nommer un dashboard « En camembert »
    ne dit rien de ce qu'il montre, et deux retouches successives produiraient deux
    tableaux de bord aux noms également muets. L'objectif, lui, est reconstruit à
    partir de la métrique, de l'axe et des filtres réellement appliqués : deux
    demandes qui aboutissent à la même analyse portent donc le même nom, et se
    partagent le même instantané au lieu d'en accumuler deux identiques.

    L'intitulé est RECONSTRUIT à partir de l'intention validée avant de retomber sur
    quoi que ce soit d'écrit ailleurs. `goal` est rédigé par le modèle, qui reprend
    volontiers la phrase de l'utilisateur mot pour mot : le nom du tableau de bord,
    qui est aussi une route et un nom de fichier, se retrouvait alors à recopier
    n'importe quel texte tapé — y compris une tentative d'injection, inoffensive
    pour la requête mais qui traînait ensuite dans dac/dashboards/.
    """
    depuis_intention = _titre_depuis_intention(intent)
    if depuis_intention:
        return depuis_intention
    return ((intent.get("goal") or "").strip() or query)


def _dashboard_name(query: str) -> str:
    """Nom affiché, dérivé de l'intitulé. C'est aussi la route DAC (/d/<nom>), donc
    on retire les caractères qui casseraient une URL ou un nom de dashboard."""
    cleaned = re.sub(r"[^\w\s'À-ÿ-]", " ", query).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > 70:
        cleaned = cleaned[:70].rsplit(" ", 1)[0] + "…"
    return cleaned.capitalize() or "Analyse"


def _write_dashboard(filename: str, name: str, description: str, widgets: list) -> None:
    dashboard = {
        "schema": "https://getbruin.com/schemas/dac/dashboard/v1",
        "name": name,
        "description": description,
        "connection": CONNECTION,
        "rows": _pack_rows(widgets),
    }
    DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    # allow_unicode : les titres et valeurs sont en français (accents) et doivent
    # rester lisibles dans le YAML versionné, pas être échappés en \uXXXX.
    contenu = yaml.dump(dashboard, Dumper=_LiteralDumper, allow_unicode=True,
                        sort_keys=False, width=120)

    # Écriture ATOMIQUE. `write_text` tronque le fichier avant de le remplir : entre
    # les deux, il est vide ou incomplet. Or DAC surveille ce dossier en rechargement
    # direct et peut le relire à cet instant précis ; et deux questions posées en même
    # temps visent le MÊME `_principal.yml`. Un remplacement d'un seul tenant supprime
    # les deux fenêtres à la fois : les lecteurs voient l'ancien fichier ou le nouveau,
    # jamais un état intermédiaire.
    #
    # Le fichier temporaire est créé dans le dossier de destination — os.replace n'est
    # atomique qu'à l'intérieur d'un même système de fichiers. Son nom porte l'identité
    # du processus et du thread pour que deux écritures simultanées ne se disputent pas
    # le même intermédiaire.
    cible = DASHBOARDS_DIR / filename
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    provisoire = TEMP_DIR / ("%s.%d.%d.tmp" % (filename, os.getpid(), threading.get_ident()))
    try:
        provisoire.write_text(contenu, encoding="utf-8")
        # Sous Windows, remplacer un fichier qu'un autre processus a ouvert échoue
        # (« Access is denied ») au lieu d'attendre. Le cas est bref — le temps d'une
        # lecture — donc quelques tentatives espacées suffisent presque toujours.
        for tentative in range(_TENTATIVES_REMPLACEMENT):
            try:
                os.replace(provisoire, cible)
                return
            except PermissionError:
                if tentative == _TENTATIVES_REMPLACEMENT - 1:
                    # PAS de repli sur une écriture directe. Elle rouvrirait
                    # exactement la fenêtre que ce mécanisme ferme, et un test de
                    # charge l'a confirmé : le lecteur voyait alors un YAML tronqué.
                    # Mieux vaut laisser en place le fichier précédent, qui est
                    # valide, et propager l'échec — `main.py` traite déjà l'écriture
                    # du tableau de bord comme non bloquante et renvoie la réponse
                    # texte, plutôt que de servir un dashboard illisible.
                    logger.warning(
                        "Remplacement de %s impossible après %d tentatives ; le "
                        "tableau de bord précédent est conservé intact.",
                        filename, _TENTATIVES_REMPLACEMENT,
                    )
                    raise
                time.sleep(_ATTENTE_REMPLACEMENT_S)
    finally:
        # Si le remplacement a échoué, l'intermédiaire ne doit pas rester derrière :
        # `_prune_generated` ne le connaît pas et il s'accumulerait sans fin.
        provisoire.unlink(missing_ok=True)


def write_main_dashboard(query: str, intent: dict, widgets: list | None = None) -> str:
    """Réécrit LE dashboard de travail et renvoie son nom — toujours le même, donc
    la même URL d'iframe d'une question à l'autre. C'est ce qui fait qu'une demande
    modifie le tableau de bord sous les yeux de l'utilisateur au lieu d'en ouvrir un
    autre. Lève si l'écriture échoue : l'appelant retombe alors sur l'instantané."""
    widgets = compose_widgets(intent) if widgets is None else widgets
    _write_dashboard(MAIN_FILENAME, MAIN_DASHBOARD_NAME,
                      _dashboard_name(_analysis_title(query, intent)), widgets)
    logger.info("Dashboard de travail réécrit pour %r (%d widgets)", query, len(widgets))
    return MAIN_DASHBOARD_NAME


# Au-delà, le tableau de bord n'est plus lisible d'un coup d'œil. Le plus ancien
# widget cède alors la place : mieux vaut une page qui reste lisible qu'une page
# complète où l'on ne trouve plus rien.
MAX_MAIN_WIDGETS = 24


def append_to_main_dashboard(query: str, intent: dict) -> tuple[str | None, bool]:
    """Ajoute UN widget au tableau de bord de travail. Renvoie (nom, ajout réel).

    Le second élément distingue « ajouté » de « déjà présent » : annoncer un ajout
    qui n'a pas eu lieu vaudrait tout autant que de ne rien dire.

    Le nom est None si ce tableau de bord n'existe pas encore : « ajoute … » n'a alors
    rien à compléter, et l'appelant retombe sur une composition normale. Volontaire —
    compléter la vue d'ensemble à la place poserait un piège, ses widgets suivant les
    filtres de période et de practice de la page, qu'un widget ajouté ne connaît pas :
    déplacer le filtre mettrait 24 widgets à jour et pas le 25e.
    """
    path = DASHBOARDS_DIR / MAIN_FILENAME
    if not path.exists():
        return None, False

    existant = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    widgets = [w for row in existant.get("rows") or [] for w in row.get("widgets", [])]

    nouveau = _primary(intent, col=6)
    if any(w.get("sql") == nouveau.get("sql") for w in widgets):
        # Déjà présent à l'identique : l'ajouter deux fois n'apprendrait rien.
        logger.info("Widget déjà présent, ajout ignoré pour %r", query)
        return MAIN_DASHBOARD_NAME, False

    widgets.append(nouveau)
    widgets = widgets[-MAX_MAIN_WIDGETS:]

    titre = existant.get("description") or ""
    ajout = _analysis_title(query, intent)
    description = f"{titre} + {ajout}" if titre else ajout
    if len(description) > 120:
        description = "…" + description[-119:]

    _write_dashboard(MAIN_FILENAME, MAIN_DASHBOARD_NAME, description, widgets)
    logger.info("Widget ajouté au tableau de bord de travail (%d au total)", len(widgets))
    return MAIN_DASHBOARD_NAME, True


def write_generated_dashboard(query: str, intent: dict, widgets: list | None = None) -> str:
    """Écrit l'INSTANTANÉ de la question et renvoie son nom (= sa route DAC).

    Le dashboard de travail est réécrit à chaque question ; cet instantané, lui,
    fige le résultat de CETTE question-là. C'est ce qui permet à la liste déroulante
    de rouvrir une analyse passée telle qu'elle était, sans repasser par le modèle.
    Lève une exception si l'écriture échoue — l'appelant décide alors de retomber
    sur l'affichage classique."""
    # Les widgets peuvent être fournis par l'appelant : le tableau de bord de travail
    # et l'instantané portent exactement les mêmes, et les composer deux fois refait
    # pour rien le comptage de cardinalité qui décide camembert ou barres.
    widgets = compose_widgets(intent) if widgets is None else widgets
    name = _dashboard_name(_analysis_title(query, intent))
    filename = _generated_filename(name)
    _write_dashboard(
        filename, name,
        "Instantané de votre question — mêmes filtres sur tous les widgets.",
        widgets,
    )
    _prune_generated(keep=filename)
    logger.info("Dashboard DAC généré : %r (%d widgets)", name, len(widgets))
    return name
