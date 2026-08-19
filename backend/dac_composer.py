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
import re
from pathlib import Path

import yaml

from .labels import DIMENSION_LABELS, METRIC_LABELS
from .sql_builder import (
    MAX_CATEGORIES, METRIC_SQL, RAW_COLUMNS, _where_clause, build_sql, funnel_sql,
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

# Un fichier par question, nommé d'après un condensé de son titre. Un fichier unique
# réécrit à chaque fois était plus simple, mais rendait tout retour en arrière
# impossible : poser une deuxième question effaçait le dashboard de la première,
# alors que l'utilisateur veut souvent comparer ses réponses successives.
GENERATED_PREFIX = "_analyse_"

# Plafond du nombre de dashboards générés conservés : au-delà, les plus anciens sont
# supprimés. Sans ce ménage, chaque question laisserait un fichier derrière elle.
MAX_GENERATED_DASHBOARDS = 12


def _generated_filename(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{GENERATED_PREFIX}{digest}.yml"


def _prune_generated(keep: str) -> None:
    """Ne garde que les MAX_GENERATED_DASHBOARDS fichiers générés les plus récents.
    `keep` est toujours conservé : c'est celui qu'on vient d'écrire."""
    try:
        fichiers = sorted(
            (f for f in DASHBOARDS_DIR.glob(f"{GENERATED_PREFIX}*.yml") if f.name != keep),
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


def _metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric).capitalize()


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
            "days_remaining": "Jours restants", "budget": "Budget",
            "win_probability": "Probabilité",
        }
        columns = []
        for name in RAW_COLUMNS:
            column = {"name": name, "label": labels.get(name, name)}
            if name == "budget":
                column["number"] = "currency"
            elif name == "days_remaining":
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
        secondary = "country" if dimension == "practice" else "practice"
        return {
            "name": title, "type": "chart", "chart": "heatmap", "col": col, "sql": sql,
            "x": {"field": secondary, "type": "category", "title": _dimension_label(secondary)},
            "y": {"field": dimension, "type": "category", "title": _dimension_label(dimension)},
            "value": {"field": metric},
        }

    # bar / line / area : même structure x/y, seul le type de tracé change.
    chart = chart_type if chart_type in ("bar", "line", "area") else "bar"
    return {
        "name": title, "type": "chart", "chart": chart, "col": col, "sql": sql,
        "x": {"field": dimension, "type": "category", "title": _dimension_label(dimension)},
        "y": {"field": metric, "type": "number", "title": _metric_label(metric), "format": fmt},
    }


def _kpi_intent(intent: dict, metric: str) -> dict:
    """Même filtres que la question, mais sans dimension : un total global."""
    return {
        "metric": metric, "dimension": "", "chart_type": "kpi_card",
        "filters": intent.get("filters") or {},
        "range_filters": intent.get("range_filters") or {},
        "exclude_statuses": intent.get("exclude_statuses") or [],
        "use_raw_table": False, "limit": 0,
    }


def _variant_intent(intent: dict, **overrides) -> dict:
    """Copie de l'intention en ne changeant que ce qui est demandé — les filtres
    de la question sont TOUJOURS conservés, pour que tous les widgets du dashboard
    parlent bien du même périmètre."""
    variant = {
        "metric": intent.get("metric") or "budget",
        "dimension": intent.get("dimension") or "",
        "chart_type": intent.get("chart_type") or "bar",
        "filters": intent.get("filters") or {},
        "range_filters": intent.get("range_filters") or {},
        "exclude_statuses": intent.get("exclude_statuses") or [],
        "use_raw_table": intent.get("use_raw_table", False),
        "limit": intent.get("limit") or 0,
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
    widgets = [_widget_from_intent(_kpi_intent(intent, metric), _metric_label(metric), col=3)]
    if metric != "nb_opportunities":
        widgets.append(_widget_from_intent(
            _kpi_intent(intent, "nb_opportunities"), "Opportunités", col=3))

    # Contexte : « part du portefeuille » n'a de sens que si un filtre restreint le
    # périmètre (sans filtre elle vaudrait toujours 100 %) — sinon on donne l'ordre
    # de grandeur unitaire, qui situe le total tout aussi bien.
    if intent.get("filters") or intent.get("range_filters"):
        widgets.append(_share_of_portfolio_widget(intent, metric, col=3))
    elif metric != "nb_opportunities":
        widgets.append(_average_widget(intent, metric, col=3))

    if metric != "weighted_amount":
        widget = _widget_from_intent(
            _kpi_intent(intent, "weighted_amount"), "Montant pondéré", col=3)
        # Mention explicite : weighted_amount est vide pour ~49 % des opportunités
        # (probabilité de gain non renseignée). Sans cette précision, le chiffre se
        # lit comme un total du portefeuille alors qu'il n'en couvre que la moitié.
        widget["description"] = (
            "Somme des seules opportunités dont la probabilité de gain est renseignée "
            "— environ la moitié du portefeuille."
        )
        widgets.append(widget)
    return widgets


def _primary(intent: dict, col: int) -> dict:
    return _widget_from_intent(intent, intent.get("goal") or "Résultat", col=col)


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
        f"{_metric_label(metric)} par {_dimension_label(complement).lower()}",
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

    C'est la réponse directe à « 72 M€, c'est beaucoup ? » : un montant absolu n'a
    aucun point de comparaison tant qu'on ne sait pas ce qu'il représente du tout.
    Ne vaut la peine que si la question filtre — sans filtre, la part vaut 100 %."""
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
    total (350 opportunités à 470 k€ n'est pas la même histoire que 10 à 16 M€)."""
    column = {"budget": "budget", "financial_offer": "financial_offer",
              "weighted_amount": "weighted_amount"}.get(metric, "budget")
    where = _where_clause(intent)
    return {
        "name": f"{_metric_label(metric)} moyen", "type": "metric", "col": col,
        "sql": f"SELECT AVG({column}) AS value\nFROM opportunities\nWHERE {where}",
        "description": "Moyenne par opportunité du périmètre.",
        "value": {"field": "value", "type": "number", "format": ",.0f"},
    }


def _share_of_total_widget(intent: dict, metric: str, col: int) -> dict:
    """Part de chaque valeur dans le total, en pourcentage. Répond à « 72 M€,
    c'est beaucoup ? » : un chiffre absolu seul n'a pas de point de comparaison."""
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
    }


def _compose_breakdown(intent: dict) -> list:
    """« budget par pays » : la répartition, plus un second axe de lecture."""
    metric = intent.get("metric") or "budget"
    widgets = _kpi_row(intent, metric)
    widgets.append(_primary(intent, col=7))
    complement = _complement_widget(intent, metric, col=5)
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
    expr = METRIC_SQL.get(metric, METRIC_SQL["budget"])
    where = _where_clause(intent)
    sql = (
        f"SELECT {axis}, {series}, {expr} AS {metric}\n"
        f"FROM opportunities\nWHERE {where}\n"
        f"GROUP BY {axis}, {series}\n"
        f"ORDER BY {axis}, {series}"
    )
    return {
        "name": f"{_metric_label(metric)} par {_dimension_label(axis).lower()} "
                 f"et {_dimension_label(series).lower()}",
        "type": "chart", "chart": "bar", "col": col, "sql": sql, "stacked": True,
        "color": {"field": series},
        "x": {"field": axis, "type": "category", "title": _dimension_label(axis)},
        "y": {"field": metric, "type": "number", "title": _metric_label(metric), "format": _fmt(metric)},
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
    return rows


def _dashboard_name(query: str) -> str:
    """Nom affiché = la question posée. C'est aussi la route DAC (/d/<nom>), donc
    on retire les caractères qui casseraient une URL ou un nom de dashboard."""
    cleaned = re.sub(r"[^\w\s'À-ÿ-]", " ", query).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > 70:
        cleaned = cleaned[:70].rsplit(" ", 1)[0] + "…"
    return cleaned.capitalize() or "Analyse"


def write_generated_dashboard(query: str, intent: dict) -> str:
    """Écrit le dashboard répondant à la question et renvoie son nom (= sa route
    DAC). Lève une exception si l'écriture échoue — l'appelant décide alors de
    retomber sur l'affichage classique."""
    widgets = compose_widgets(intent)
    name = _dashboard_name(query)
    dashboard = {
        "schema": "https://getbruin.com/schemas/dac/dashboard/v1",
        "name": name,
        "description": "Dashboard généré à partir de votre question — mêmes filtres sur tous les widgets.",
        "connection": CONNECTION,
        "rows": _pack_rows(widgets),
    }

    DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    filename = _generated_filename(name)
    path = DASHBOARDS_DIR / filename
    # allow_unicode : les titres et valeurs sont en français (accents) et doivent
    # rester lisibles dans le YAML versionné, pas être échappés en \uXXXX.
    path.write_text(
        yaml.dump(dashboard, Dumper=_LiteralDumper, allow_unicode=True,
                   sort_keys=False, width=120),
        encoding="utf-8",
    )
    _prune_generated(keep=filename)
    logger.info("Dashboard DAC généré : %r (%d widgets)", name, len(widgets))
    return name
