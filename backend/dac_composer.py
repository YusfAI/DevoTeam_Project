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
import logging
import re
from pathlib import Path

import yaml

from .labels import DIMENSION_LABELS, METRIC_LABELS
from .sql_builder import RAW_COLUMNS, build_sql

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

# Fichier unique réécrit à chaque question : le nom AFFICHÉ change (c'est lui qui
# sert de route à DAC), mais garder un seul fichier évite d'accumuler des centaines
# de dashboards jetables dans le dépôt.
GENERATED_FILENAME = "_analyse.yml"

CONNECTION = "devoteam_duckdb"

# Ordre de préférence pour la dimension complémentaire : la plus parlante d'abord.
# On ne prend jamais la dimension déjà affichée, NI une dimension figée par un filtre
# de la question — grouper par practice alors que la question filtre déjà sur une
# seule practice produirait un graphique à une seule barre, sans aucune information.
_COMPLEMENT_PREFERENCE = ["practice", "country", "status", "funding_source", "opp_type", "deadline_month"]


def _complementary_dimension(intent: dict) -> str:
    primary = intent.get("dimension") or ""
    pinned = set((intent.get("filters") or {}).keys())
    for candidate in _COMPLEMENT_PREFERENCE:
        if candidate != primary and candidate not in pinned:
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
    """Règles déterministes : l'angle principal de la question, entouré de widgets
    complémentaires qui partagent ses filtres."""
    metric = intent.get("metric") or "budget"
    chart_type = intent.get("chart_type") or "bar"
    widgets = []

    # --- Ligne 1 : les totaux du périmètre interrogé ---
    widgets.append(_widget_from_intent(
        _kpi_intent(intent, metric), _metric_label(metric), col=4))
    if metric != "nb_opportunities":
        widgets.append(_widget_from_intent(
            _kpi_intent(intent, "nb_opportunities"), "Opportunités", col=4))
    if metric != "weighted_amount":
        widgets.append(_widget_from_intent(
            _kpi_intent(intent, "weighted_amount"), "Montant pondéré", col=4))

    # --- Le graphique qui répond directement à la question ---
    primary_title = intent.get("goal") or "Résultat"
    primary_col = 12 if chart_type in ("table", "scatter", "heatmap") else 7
    widgets.append(_widget_from_intent(intent, primary_title, col=primary_col))

    # --- Le même chiffre vu sous un autre angle ---
    complement = _complementary_dimension(intent)
    if complement and chart_type not in ("table", "scatter"):
        widgets.append(_widget_from_intent(
            _variant_intent(intent, dimension=complement, chart_type="pie",
                             use_raw_table=False, limit=0),
            f"{_metric_label(metric)} par {_dimension_label(complement).lower()}",
            col=5 if primary_col == 7 else 6,
        ))

    # --- Où en est le pipeline sur ce périmètre ---
    if chart_type != "funnel":
        widgets.append(_widget_from_intent(
            _variant_intent(intent, metric="nb_opportunities", dimension="status",
                             chart_type="funnel", use_raw_table=False, limit=0),
            "Pipeline commercial",
            col=6,
        ))

    # --- Le détail, pour vérifier les chiffres ligne par ligne ---
    if chart_type != "table" and not intent.get("use_raw_table"):
        widgets.append(_widget_from_intent(
            _variant_intent(intent, chart_type="table", use_raw_table=True, limit=0),
            "Détail des opportunités",
            col=6 if chart_type != "funnel" else 12,
        ))

    return widgets


def _pack_rows(widgets: list) -> list:
    """Répartit les widgets en lignes de 12 colonnes (la grille DAC)."""
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
    path = DASHBOARDS_DIR / GENERATED_FILENAME
    # allow_unicode : les titres et valeurs sont en français (accents) et doivent
    # rester lisibles dans le YAML versionné, pas être échappés en \uXXXX.
    path.write_text(
        yaml.dump(dashboard, Dumper=_LiteralDumper, allow_unicode=True,
                   sort_keys=False, width=120),
        encoding="utf-8",
    )
    logger.info("Dashboard DAC généré : %r (%d widgets)", name, len(widgets))
    return name
