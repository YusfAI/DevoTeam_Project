from .labels import DIMENSION_LABELS, METRIC_LABELS

# Palette catégorielle validée (ordre fixe, CVD-safe) — utilisée uniquement pour
# les camemberts (plusieurs catégories affichées côte à côte, l'écart CVD entre
# teintes voisines compte). Ne pas modifier l'ordre sans revalider les paires.
CATEGORICAL_PALETTE = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#e34948",
]

# Teinte de marque Devoteam pour les graphiques à SÉRIE UNIQUE (bar/line) — un seul
# hue affiché à la fois, donc aucun risque d'ambiguïté CVD entre teintes voisines ;
# indépendante de CATEGORICAL_PALETTE pour ne pas perturber sa validation.
ACCENT = "#f2405a"

# Au-delà de ces seuils, un pie/bar devient illisible : on regroupe la traîne dans
# "Autres" plutôt que d'afficher toutes les catégories.
MAX_PIE_SLICES = 6
MAX_BAR_CATEGORIES = 12


def _dimension_title(dimension: str) -> str:
    return DIMENSION_LABELS.get(dimension, dimension.replace("_", " ")).capitalize()


def _metric_title(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ")).capitalize()


def _cap_categories(data: list, dimension: str, metric: str, aggregation: str, max_n: int) -> list:
    """Limite le nombre de catégories affichées. Pour sum/count, la traîne est
    regroupée dans une catégorie "Autres" (additionner des sommes/comptages a un
    sens). Pour avg (ex: win_probability), on tronque simplement au top N — calculer
    une moyenne-de-moyennes fabriquerait un chiffre qui n'existe pas dans les données.
    """
    if len(data) <= max_n or not dimension:
        return data

    sortable = sorted(data, key=lambda r: (r.get(metric) is None, -(r.get(metric) or 0)))
    head = sortable[: max_n - 1]
    tail = sortable[max_n - 1:]

    if aggregation not in ("sum", "count") or not tail:
        return sortable[:max_n]

    tail_values = [r.get(metric) for r in tail if r.get(metric) is not None]
    other_row = {dimension: "Autres", metric: sum(tail_values) if tail_values else None}
    return head + [other_row]


def build_vega_spec(intent: dict, data: list) -> dict:
    metric = intent.get("metric", "budget")
    dimension = intent.get("dimension", "")
    chart_type = intent.get("chart_type", "bar")
    aggregation = intent.get("aggregation", "sum")
    title_text = intent.get("goal", f"{metric} par {dimension}")

    if not data:
        return {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": title_text,
            "data": {"values": []},
            "mark": {"type": "text", "fontSize": 16, "color": "#64748b"},
            "encoding": {"text": {"value": "Aucune donnée à afficher"}},
        }

    if metric == "win_probability":
        # Stocké en base comme fraction 0-1 (0.74 = 74%) — jamais affiché tel quel,
        # sinon le graphique montre "0.7 %" au lieu de "74 %".
        data = [
            {**row, "win_probability": None if row.get("win_probability") is None else row["win_probability"] * 100}
            for row in data
        ]

    # Un pie avec trop de tranches est illisible (dataviz: ≤ 6 segments) — on bascule
    # sur une barre horizontale plutôt que de forcer un camembert surchargé.
    horizontal = False
    if chart_type == "pie" and dimension and len(data) > MAX_PIE_SLICES:
        chart_type = "bar"
        horizontal = True

    if dimension and chart_type in ("bar", "pie"):
        max_n = MAX_PIE_SLICES if chart_type == "pie" else MAX_BAR_CATEGORIES
        data = _cap_categories(data, dimension, metric, aggregation, max_n)

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": title_text,
        "title": {"text": title_text, "fontSize": 16, "anchor": "start"},
        "data": {"values": data},
        "width": "container",
        "height": 380,
        "padding": {"left": 10, "right": 10, "top": 10, "bottom": 10},
        "transform": [{"filter": f"datum.{metric} != null"}],
    }

    fmt = ",.0f" if metric != "win_probability" else ".1f"
    suffix = " €" if metric in ("budget", "financial_offer", "weighted_amount") else ""
    if metric == "win_probability":
        suffix = " %"

    if chart_type == "bar" and horizontal:
        spec["mark"] = {"type": "bar", "tooltip": True, "cornerRadiusEnd": 4, "color": ACCENT}
        spec["encoding"] = {
            "y": {
                "field": dimension,
                "type": "nominal",
                "sort": "-x",
                "axis": {"labelLimit": 160},
                "title": _dimension_title(dimension),
            },
            "x": {
                "field": metric,
                "type": "quantitative",
                "title": _metric_title(metric),
                "axis": {"format": fmt, "labelExpr": f"format(datum.value, '{fmt}') + '{suffix}'"},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt, "title": metric},
            ],
        }

    elif chart_type == "bar":
        spec["mark"] = {"type": "bar", "tooltip": True, "cornerRadiusEnd": 4, "color": ACCENT}
        spec["encoding"] = {
            "x": {
                "field": dimension,
                "type": "nominal",
                "sort": "-y",
                "axis": {"labelAngle": -35, "labelLimit": 120},
                "title": _dimension_title(dimension),
            },
            "y": {
                "field": metric,
                "type": "quantitative",
                "title": _metric_title(metric),
                "axis": {"format": fmt, "labelExpr": f"format(datum.value, '{fmt}') + '{suffix}'"},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt, "title": metric},
            ],
        }

    elif chart_type == "pie":
        spec["mark"] = {"type": "arc", "innerRadius": 60, "outerRadius": 140, "tooltip": True}
        spec["encoding"] = {
            "theta": {"field": metric, "type": "quantitative", "stack": True},
            "color": {
                "field": dimension,
                "type": "nominal",
                "scale": {"range": CATEGORICAL_PALETTE},
                "legend": {"orient": "right", "columns": 1, "title": _dimension_title(dimension)},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt},
            ],
        }

    elif chart_type == "line":
        spec["mark"] = {"type": "line", "point": {"size": 60}, "tooltip": True, "color": ACCENT, "strokeWidth": 2.5}
        spec["encoding"] = {
            "x": {
                "field": dimension,
                "type": "ordinal",
                "sort": None,
                "title": _dimension_title(dimension),
                "axis": {"labelAngle": -45},
            },
            "y": {
                "field": metric,
                "type": "quantitative",
                "title": _metric_title(metric),
                "axis": {"format": fmt},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt},
            ],
        }

    return spec
