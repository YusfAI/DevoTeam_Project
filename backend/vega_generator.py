def build_vega_spec(intent: dict, data: list) -> dict:
    metric     = intent.get('metric', 'budget')
    dimension  = intent.get('dimension', '')
    chart_type = intent.get('chart_type', 'bar')
    use_raw    = intent.get('use_raw_table', False) or bool(intent.get('range_filters'))
    title_text = intent.get('goal', f"{metric} by {dimension}")

    # --- TABLE / Brute list ---
    # Vega-Lite doesn't support traditional HTML tables natively.
    # We build a point+text layer for each important column instead.
    if chart_type == "table" or use_raw:
        COLUMNS = ["country", "practice", "status", "buyer", "budget", "win_probability", "days_remaining", "deadline"]
        # Only use columns that actually exist in the data
        cols = [c for c in COLUMNS if data and c in data[0]]
        
        return {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": title_text,
            "title": title_text,
            "data": {"values": data},
            "width": "container",
            "mark": {"type": "text", "align": "left"},
            "transform": [{"window": [{"op": "row_number", "as": "row"}]}],
            "encoding": {
                "y": {"field": "row", "type": "ordinal", "axis": None},
                "x": {"field": cols[0] if cols else "country", "type": "nominal"},
                "text": {"field": cols[0] if cols else "country", "type": "nominal"},
                "tooltip": [{"field": c, "type": "nominal" if c in ("country","practice","status","buyer","deadline") else "quantitative"} for c in cols]
            }
        }

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": title_text,
        "title": title_text,
        "data": {"values": data},
        "width": "container",
        "height": "container",
        "transform": [
            {"filter": f"datum.{metric} != null"}
        ]
    }

    agg = intent.get('aggregation', 'sum')
    if agg not in ['sum', 'average', 'count']:
        agg = 'sum'

    if chart_type == "bar":
        spec["mark"] = {"type": "bar", "tooltip": True, "cornerRadiusEnd": 4, "color": "#3b82f6"}
        spec["encoding"] = {
            "x": {"field": dimension, "type": "nominal", "sort": "-y", "axis": {"labelAngle": -45}},
            "y": {"field": metric, "type": "quantitative", "aggregate": agg}
        }
    elif chart_type == "pie":
        spec["mark"] = {"type": "arc", "innerRadius": 50, "tooltip": True}
        spec["encoding"] = {
            "theta": {"field": metric, "type": "quantitative", "aggregate": agg},
            "color": {"field": dimension, "type": "nominal"}
        }
    elif chart_type == "line":
        spec["mark"] = {"type": "line", "point": True, "tooltip": True, "color": "#10b981"}
        spec["encoding"] = {
            "x": {"field": dimension, "type": "nominal"},
            "y": {"field": metric, "type": "quantitative", "aggregate": agg}
        }
    elif chart_type == "kpi_card":
        spec["mark"] = {"type": "text", "fontSize": 48, "fontWeight": "bold", "color": "#0f172a"}
        spec["encoding"] = {
            "text": {"field": metric, "type": "quantitative", "aggregate": agg, "format": ",.0f"}
        }

    return spec
