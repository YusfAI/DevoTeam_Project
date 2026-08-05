def build_vega_spec(intent: dict, data: list) -> dict:
    metric = intent.get("metric", "budget")
    dimension = intent.get("dimension", "")
    chart_type = intent.get("chart_type", "bar")
    title_text = intent.get("goal", f"{metric} par {dimension}")

    if not data:
        return {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": title_text,
            "data": {"values": []},
            "mark": {"type": "text", "fontSize": 16, "color": "#64748b"},
            "encoding": {"text": {"value": "Aucune donnée à afficher"}},
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

    if chart_type == "bar":
        spec["mark"] = {"type": "bar", "tooltip": True, "cornerRadiusEnd": 4, "color": "#3b82f6"}
        spec["encoding"] = {
            "x": {
                "field": dimension,
                "type": "nominal",
                "sort": "-y",
                "axis": {"labelAngle": -35, "labelLimit": 120},
                "title": dimension.replace("_", " ").capitalize(),
            },
            "y": {
                "field": metric,
                "type": "quantitative",
                "title": metric.replace("_", " ").capitalize(),
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
                "legend": {"orient": "right", "columns": 1},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt},
            ],
        }

    elif chart_type == "line":
        spec["mark"] = {"type": "line", "point": {"size": 60}, "tooltip": True, "color": "#10b981", "strokeWidth": 2.5}
        spec["encoding"] = {
            "x": {
                "field": dimension,
                "type": "ordinal",
                "sort": None,
                "title": "Mois",
                "axis": {"labelAngle": -45},
            },
            "y": {
                "field": metric,
                "type": "quantitative",
                "title": metric.replace("_", " ").capitalize(),
                "axis": {"format": fmt},
            },
            "tooltip": [
                {"field": dimension, "type": "nominal"},
                {"field": metric, "type": "quantitative", "format": fmt},
            ],
        }

    elif chart_type == "kpi_card":
        val = data[0].get(metric, 0) or 0
        if metric in ("budget", "financial_offer", "weighted_amount"):
            display = f"{val:,.0f} €".replace(",", " ")
        elif metric == "nb_opportunities":
            display = f"{int(val):,}".replace(",", " ")
        elif metric == "win_probability":
            display = f"{float(val):.1f} %"
        else:
            display = str(val)

        spec["height"] = 200
        spec["layer"] = [
            {
                "mark": {"type": "text", "fontSize": 14, "color": "#64748b", "dy": -30},
                "encoding": {"text": {"value": title_text}},
            },
            {
                "mark": {"type": "text", "fontSize": 52, "fontWeight": "bold", "color": "#0f172a"},
                "encoding": {"text": {"value": display}},
            },
        ]
        del spec["transform"]
        del spec["encoding"]

    return spec
