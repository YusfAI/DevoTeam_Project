"""Build user-facing messages strictly from query results (no LLM hallucination)."""

METRIC_LABELS = {
    "budget": "budget",
    "financial_offer": "offre financière",
    "weighted_amount": "montant pondéré",
    "nb_opportunities": "nombre d'opportunités",
    "win_probability": "probabilité de gain moyenne",
}

DIMENSION_LABELS = {
    "country": "pays",
    "practice": "practice",
    "status": "statut",
    "deadline_month": "mois d'échéance",
    "deadline_year": "année d'échéance",
    "funding_source": "source de financement",
    "opp_type": "type d'opportunité",
}

FILTER_LABELS = {
    "country": "pays",
    "practice": "practice",
    "status": "statut",
    "funding_source": "source de financement",
    "opp_type": "type",
    "partner": "partenaire",
}


def get_help_message() -> str:
    return (
        "Je peux analyser uniquement les données d'opportunités commerciales disponibles.\n\n"
        "Exemples :\n"
        "• « budget par pays pour Risk Advisory »\n"
        "• « combien d'offres gagnées ? »\n"
        "• « top 5 pays par budget »\n"
        "• « évolution du budget par mois pour Data Management »\n"
        "• « liste des opportunités urgentes (< 7 jours) »"
    )


def _format_value(value, metric: str) -> str:
    if value is None:
        return "N/A"
    if metric == "win_probability":
        return f"{float(value):.1f} %"
    if metric == "nb_opportunities":
        return f"{int(value):,}".replace(",", " ")
    return f"{float(value):,.0f} €".replace(",", " ")


def _metric_value(row: dict, metric: str):
    val = row.get(metric)
    if val is None and metric == "budget":
        val = row.get("total_budget")
    if val is None and metric == "financial_offer":
        val = row.get("total_offer")
    if val is None and metric == "weighted_amount":
        val = row.get("total_weighted")
    return val


def _describe_filters(intent: dict) -> str:
    parts = []
    for key, value in intent.get("filters", {}).items():
        label = FILTER_LABELS.get(key, key)
        parts.append(f"{label} = {value}")
    for key, rule in intent.get("range_filters", {}).items():
        label = FILTER_LABELS.get(key, key)
        op = rule.get("op", "")
        value = rule.get("value", "")
        parts.append(f"{label} {op} {value}")
    if not parts:
        return ""
    return " — filtres : " + ", ".join(parts)


def _top_entries(rows_with_values: list, metric: str, n: int = 3) -> str:
    sorted_rows = sorted(rows_with_values, key=lambda x: x[1], reverse=True)[:n]
    total = sum(v for _, v in rows_with_values)
    parts = []
    for dim, val in sorted_rows:
        pct = (val / total * 100) if total else 0
        parts.append(f"{dim} ({_format_value(val, metric)}, {pct:.0f} %)")
    return " | ".join(parts)


def build_data_response(intent: dict, data: list) -> str:
    metric = intent.get("metric", "budget")
    dimension = intent.get("dimension", "")
    chart_type = intent.get("chart_type", "bar")
    goal = intent.get("goal", "")
    use_raw = intent.get("use_raw_table") or bool(intent.get("range_filters"))
    filter_desc = _describe_filters(intent)
    metric_label = METRIC_LABELS.get(metric, metric)
    limit = int(intent.get("limit") or 0)

    if not data:
        return f"Aucune donnée trouvée{filter_desc}. Essayez d'élargir vos critères."

    if use_raw or chart_type == "table":
        budgets = [_metric_value(r, "budget") for r in data]
        budgets = [b for b in budgets if b is not None]
        total_budget = sum(budgets) if budgets else 0
        suffix = f" Budget total : {_format_value(total_budget, 'budget')}." if budgets else ""
        return f"{len(data)} opportunité(s){filter_desc}.{suffix}"

    if chart_type == "kpi_card" or (not dimension and len(data) == 1):
        val = _metric_value(data[0], metric)
        label = goal or metric_label.capitalize()
        return f"{label} : {_format_value(val, metric)}."

    if dimension:
        dim_label = DIMENSION_LABELS.get(dimension, dimension)
        rows_with_values = []
        for row in data:
            val = _metric_value(row, metric)
            if val is not None:
                rows_with_values.append((row.get(dimension, "?"), float(val)))

        if not rows_with_values:
            return f"Aucune valeur de {metric_label} disponible{filter_desc}."

        total = sum(v for _, v in rows_with_values)
        top_line = _top_entries(rows_with_values, metric, 3)
        prefix = f"{goal} — " if goal else ""
        limit_note = f" (top {limit})" if limit > 0 else ""
        return (
            f"{prefix}{metric_label.capitalize()} par {dim_label}{filter_desc}{limit_note}. "
            f"Total : {_format_value(total, metric)} sur {len(rows_with_values)} {dim_label}(s). "
            f"Classement : {top_line}."
        )

    val = _metric_value(data[0], metric)
    return f"Résultat{filter_desc} : {_format_value(val, metric)}."
