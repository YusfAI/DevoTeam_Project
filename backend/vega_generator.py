from .labels import DIMENSION_LABELS, METRIC_LABELS
from .schema_and_whitelist import KNOWN_VALUES

# Practice a exactement 3 valeurs fixes en base — la seule dimension catégorielle
# du jeu de données qui reste sous le plafond "3" imposé par le skill dataviz aux
# formes toutes-paires (scatter/bubble) sans avoir besoin de plier une traîne.
KNOWN_PRACTICES = KNOWN_VALUES["practice"]

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

# Au-delà, une carte de chaleur pays × practice devient illisible (trop de lignes) —
# on garde les N valeurs de la dimension principale les plus fortes (par le metric
# demandé), plutôt que de tronquer arbitrairement ou de tout afficher.
MAX_HEATMAP_ROWS = 15

# Rampe séquentielle validée dataviz (bleu, du plus clair au plus foncé) pour
# l'encodage de magnitude d'une carte de chaleur — deux bornes suffisent, Vega-Lite
# interpole linéairement entre elles (palette.md : étapes 100 -> 700).
HEATMAP_COLOR_RANGE = ["#cde2fb", "#0d366b"]

# Ordre du pipeline commercial, du premier contact à la signature — seules les étapes
# "en cours" font partie de l'entonnoir ; les sorties (perdu/infructueux/NO GO/hors
# scope/non shortlisté) sont des sorties du pipeline, pas des étapes séquentielles
# que traverse chaque opportunité, donc elles n'y figurent pas.
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

# Rampe ordinale validée dataviz pour un entonnoir (étapes discrètes ordonnées) — ne
# jamais démarrer plus clair que l'étape 250 (contraste ≥ 2:1 sur fond clair).
FUNNEL_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281"]


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


def _cap_heatmap_rows(data: list, dimension: str, metric: str, max_n: int = MAX_HEATMAP_ROWS) -> tuple[list, list]:
    """Garde les max_n valeurs de `dimension` au total le plus élevé sur `metric`
    (additionné sur toutes les colonnes secondaires), et renvoie aussi cet ordre
    pour piloter le tri de l'axe — sans ce tri explicite, l'ordre alphabétique par
    défaut de Vega-Lite masquerait les combinaisons les plus fortes dans la masse."""
    totals: dict = {}
    for row in data:
        key = row.get(dimension)
        val = row.get(metric) or 0
        totals[key] = totals.get(key, 0) + val

    ordered_keys = [k for k, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:max_n]]
    kept = set(ordered_keys)
    filtered = [row for row in data if row.get(dimension) in kept]
    return filtered, ordered_keys


def _build_funnel_rows(data: list, dimension: str, metric: str) -> list:
    """Reclasse les lignes selon l'ordre fixe du pipeline commercial (FUNNEL_STAGE_ORDER)
    et précalcule la géométrie symétrique (x_start/x_end centrés sur 0) qu'un entonnoir
    Vega-Lite ne sait pas produire nativement à partir d'un simple champ de valeur."""
    by_stage = {row.get(dimension): row for row in data}
    rows = []
    for i, stage in enumerate(FUNNEL_STAGE_ORDER):
        row = by_stage.get(stage)
        if row is None:
            continue
        value = row.get(metric)
        if value is None:
            continue
        half = value / 2
        rows.append({
            "stage": stage,
            metric: value,
            "x_start": -half,
            "x_end": half,
            "color_step": FUNNEL_RAMP[min(i, len(FUNNEL_RAMP) - 1)],
        })
    return rows


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

    heatmap_dim_order: list = []
    if chart_type == "heatmap" and dimension:
        data, heatmap_dim_order = _cap_heatmap_rows(data, dimension, metric)

    if chart_type == "funnel" and dimension:
        data = _build_funnel_rows(data, dimension, metric)
        if not data:
            # Aucune étape connue du pipeline dans ces données (ex: filtre trop
            # restrictif) — message clair plutôt qu'un entonnoir vide silencieux.
            return {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "title": title_text,
                "data": {"values": []},
                "mark": {"type": "text", "fontSize": 16, "color": "#64748b"},
                "encoding": {"text": {"value": "Aucune étape du pipeline trouvée dans ces données"}},
            }

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

    elif chart_type == "area":
        # Remplissage en dégradé (blanc -> teinte de marque) plutôt qu'un aplat saturé —
        # même donnée qu'une courbe "line", plus impactant visuellement pour une tendance.
        spec["mark"] = {
            "type": "area",
            "line": {"color": ACCENT, "strokeWidth": 2.5},
            "point": {"size": 50, "color": ACCENT},
            "tooltip": True,
            "color": {
                "x1": 1, "y1": 1, "x2": 1, "y2": 0, "gradient": "linear",
                "stops": [{"offset": 0, "color": "#ffffff"}, {"offset": 1, "color": ACCENT}],
            },
        }
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

    elif chart_type == "scatter":
        # Corrélation budget / probabilité de gain — metric est forcé à "budget" en amont
        # (intent_refiner.py) donc le filtre générique ci-dessus ne couvre que cet axe ;
        # on le complète pour exclure aussi les lignes sans probabilité de gain renseignée.
        spec["transform"] = [{"filter": "datum.budget != null && datum.win_probability != null"}]
        spec["mark"] = {"type": "circle", "opacity": 0.72, "tooltip": True}
        spec["encoding"] = {
            "x": {
                "field": "budget",
                "type": "quantitative",
                "title": "Budget (€)",
                "axis": {"format": ",.0f"},
            },
            "y": {
                "field": "win_probability",
                "type": "quantitative",
                "title": "Probabilité de gain",
                "axis": {"format": ".0%"},
            },
            "size": {
                "field": "weighted_amount",
                "type": "quantitative",
                "title": "Montant pondéré",
                "scale": {"range": [40, 900]},
            },
            "color": {
                "field": "practice",
                "type": "nominal",
                "scale": {"domain": KNOWN_PRACTICES, "range": CATEGORICAL_PALETTE[: len(KNOWN_PRACTICES)]},
                "legend": {"title": "Practice"},
            },
            "tooltip": [
                {"field": "buyer", "type": "nominal", "title": "Client"},
                {"field": "country", "type": "nominal", "title": "Pays"},
                {"field": "practice", "type": "nominal", "title": "Practice"},
                {"field": "status", "type": "nominal", "title": "Statut"},
                {"field": "budget", "type": "quantitative", "format": ",.0f", "title": "Budget (€)"},
                {"field": "win_probability", "type": "quantitative", "format": ".0%", "title": "Probabilité de gain"},
            ],
        }

    elif chart_type == "heatmap":
        secondary = "country" if dimension == "practice" else "practice"
        spec["encoding"] = {
            "y": {
                "field": dimension,
                "type": "nominal",
                "sort": heatmap_dim_order or None,
                "title": _dimension_title(dimension),
                "axis": {"labelLimit": 160},
            },
            "x": {
                "field": secondary,
                "type": "nominal",
                "title": _dimension_title(secondary),
                "axis": {"labelAngle": -30},
            },
            "color": {
                "field": metric,
                "type": "quantitative",
                "title": _metric_title(metric),
                "scale": {"range": HEATMAP_COLOR_RANGE},
                "legend": {"format": fmt},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": secondary, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt},
            ],
        }
        spec["mark"] = {"type": "rect", "tooltip": True, "cornerRadius": 2}

    elif chart_type == "funnel":
        stage_order = [row["stage"] for row in data]
        spec["transform"] = []
        spec["layer"] = [
            {
                "mark": {"type": "bar", "tooltip": True, "cornerRadius": 2},
                "encoding": {
                    "y": {
                        "field": "stage", "type": "nominal", "sort": stage_order,
                        "title": None, "axis": {"labelLimit": 200},
                    },
                    "x": {"field": "x_start", "type": "quantitative", "axis": None},
                    "x2": {"field": "x_end"},
                    "color": {
                        "field": "stage", "type": "nominal",
                        "scale": {"domain": stage_order, "range": [row["color_step"] for row in data]},
                        "legend": None,
                    },
                    "tooltip": [
                        {"field": "stage", "type": "nominal", "title": "Étape"},
                        {"field": metric, "type": "quantitative", "format": fmt, "title": _metric_title(metric)},
                    ],
                },
            },
            {
                "mark": {"type": "text", "align": "center", "baseline": "middle", "fontWeight": 600,
                         "fontSize": 11, "color": "#ffffff"},
                "encoding": {
                    "y": {"field": "stage", "type": "nominal", "sort": stage_order},
                    "x": {"datum": 0, "type": "quantitative"},
                    "text": {"field": metric, "type": "quantitative", "format": fmt},
                },
            },
        ]

    return spec
