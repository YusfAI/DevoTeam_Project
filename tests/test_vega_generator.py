from backend.vega_generator import (
    build_vega_spec, MAX_BAR_CATEGORIES, MAX_HEATMAP_ROWS, KNOWN_PRACTICES, HEATMAP_COLOR_RANGE,
)


def _base_intent(**overrides):
    intent = {
        "goal": "Test", "metric": "budget", "dimension": "country",
        "chart_type": "bar", "aggregation": "sum",
    }
    intent.update(overrides)
    return intent


def test_null_values_are_filtered_client_side_not_zeroed():
    data = [
        {"country": "France", "budget": 1000000},
        {"country": "Germany", "budget": None},
    ]
    spec = build_vega_spec(_base_intent(), data)
    assert spec["transform"] == [{"filter": "datum.budget != null"}]
    # The raw None value must still reach the client as null, never coerced to 0.
    assert spec["data"]["values"][1]["budget"] is None


def test_kpi_card_is_no_longer_handled_here():
    # KPI values are now computed in Python (main.py) where None stays None natively.
    # vega_generator must not build a text-mark hack for it anymore.
    spec = build_vega_spec(_base_intent(chart_type="kpi_card"), [{"budget": 42}])
    assert "layer" not in spec
    assert "mark" not in spec


def test_bar_high_cardinality_folds_tail_into_autres():
    data = [{"country": f"C{i}", "budget": (20 - i) * 1000} for i in range(20)]
    spec = build_vega_spec(_base_intent(chart_type="bar"), data)
    values = spec["data"]["values"]
    assert len(values) == MAX_BAR_CATEGORIES
    assert values[-1]["country"] == "Autres"
    # "Autres" should hold the summed tail, not a fabricated single-row value.
    tail_sum = sum((20 - i) * 1000 for i in range(MAX_BAR_CATEGORIES - 1, 20))
    assert values[-1]["budget"] == tail_sum


def test_avg_aggregation_truncates_without_fabricating_autres():
    data = [{"status": f"S{i}", "win_probability": i} for i in range(20)]
    spec = build_vega_spec(
        _base_intent(metric="win_probability", dimension="status", chart_type="bar", aggregation="avg"),
        data,
    )
    values = spec["data"]["values"]
    assert len(values) == MAX_BAR_CATEGORIES
    assert all(v["status"] != "Autres" for v in values)


def test_pie_beyond_slice_cap_switches_to_horizontal_bar():
    # 10 categories: too many for a pie (cap 6) but fine for a bar (cap 12) — the
    # downgrade to bar is precisely so we don't need to fold these into "Autres".
    data = [{"status": f"S{i}", "nb_opportunities": 20 - i} for i in range(10)]
    spec = build_vega_spec(
        _base_intent(metric="nb_opportunities", dimension="status", chart_type="pie", aggregation="sum"),
        data,
    )
    assert spec["mark"]["type"] == "bar"
    assert spec["encoding"]["y"]["field"] == "status"
    assert spec["encoding"]["x"]["field"] == "nb_opportunities"
    assert len(spec["data"]["values"]) == 10


def test_pie_downgraded_to_bar_still_respects_the_bar_cap():
    data = [{"status": f"S{i}", "nb_opportunities": 20 - i} for i in range(16)]
    spec = build_vega_spec(
        _base_intent(metric="nb_opportunities", dimension="status", chart_type="pie", aggregation="sum"),
        data,
    )
    assert spec["mark"]["type"] == "bar"
    assert len(spec["data"]["values"]) == MAX_BAR_CATEGORIES
    assert spec["data"]["values"][-1]["status"] == "Autres"


def test_pie_within_cap_keeps_pie_and_uses_fixed_palette():
    data = [{"practice": p, "nb_opportunities": n} for p, n in [
        ("Digital Transformation", 10), ("Risk Advisory", 8), ("Data Management", 5),
    ]]
    spec = build_vega_spec(
        _base_intent(metric="nb_opportunities", dimension="practice", chart_type="pie", aggregation="sum"),
        data,
    )
    assert spec["mark"]["type"] == "arc"
    assert spec["encoding"]["color"]["scale"]["range"][0] == "#2a78d6"


def test_win_probability_is_scaled_from_fraction_to_percent():
    data = [
        {"status": "Offre gagnée", "win_probability": 0.8},
        {"status": "Lead", "win_probability": None},
    ]
    spec = build_vega_spec(
        _base_intent(metric="win_probability", dimension="status", chart_type="bar", aggregation="avg"),
        data,
    )
    values = spec["data"]["values"]
    assert values[0]["win_probability"] == 80.0
    assert values[1]["win_probability"] is None


def test_empty_data_returns_placeholder_without_crashing():
    spec = build_vega_spec(_base_intent(), [])
    assert spec["data"]["values"] == []
    assert "transform" not in spec


# ---------------------------------------------------------------------------
# area
# ---------------------------------------------------------------------------

def test_area_has_gradient_fill_and_same_shape_as_line():
    data = [{"deadline_month": "2026-01", "budget": 1000}, {"deadline_month": "2026-02", "budget": 2000}]
    spec = build_vega_spec(
        _base_intent(dimension="deadline_month", chart_type="area"),
        data,
    )
    assert spec["mark"]["type"] == "area"
    assert spec["mark"]["line"]["color"] == "#f2405a"
    assert spec["mark"]["color"]["gradient"] == "linear"
    assert spec["encoding"]["x"]["field"] == "deadline_month"
    assert spec["encoding"]["y"]["field"] == "budget"


# ---------------------------------------------------------------------------
# scatter
# ---------------------------------------------------------------------------

def _scatter_data():
    return [
        {"buyer": "ACME", "country": "France", "practice": "Risk Advisory", "status": "Offre remise",
         "budget": 100000, "win_probability": 0.6, "weighted_amount": 60000},
        {"buyer": "BIAT", "country": "Maroc", "practice": "Digital Transformation", "status": "Lead",
         "budget": 200000, "win_probability": None, "weighted_amount": None},
    ]


def test_scatter_encodes_budget_win_probability_size_and_practice_color():
    spec = build_vega_spec(_base_intent(dimension="", chart_type="scatter"), _scatter_data())
    assert spec["mark"]["type"] == "circle"
    enc = spec["encoding"]
    assert enc["x"]["field"] == "budget"
    assert enc["y"]["field"] == "win_probability"
    assert enc["size"]["field"] == "weighted_amount"
    assert enc["color"]["field"] == "practice"
    assert enc["color"]["scale"]["domain"] == KNOWN_PRACTICES
    assert len(enc["color"]["scale"]["range"]) == len(KNOWN_PRACTICES)


def test_scatter_filters_rows_missing_either_axis_client_side():
    spec = build_vega_spec(_base_intent(dimension="", chart_type="scatter"), _scatter_data())
    assert spec["transform"] == [{"filter": "datum.budget != null && datum.win_probability != null"}]
    # The raw row (including its None win_probability) still reaches the client —
    # filtering happens in Vega, never by silently dropping rows in Python.
    assert spec["data"]["values"][1]["win_probability"] is None


# ---------------------------------------------------------------------------
# heatmap
# ---------------------------------------------------------------------------

def test_heatmap_crosses_dimension_with_practice_by_default():
    data = [
        {"country": "France", "practice": "Risk Advisory", "budget": 100000},
        {"country": "France", "practice": "Data Management", "budget": 50000},
        {"country": "Maroc", "practice": "Risk Advisory", "budget": 80000},
    ]
    spec = build_vega_spec(_base_intent(dimension="country", chart_type="heatmap"), data)
    assert spec["mark"]["type"] == "rect"
    assert spec["encoding"]["y"]["field"] == "country"
    assert spec["encoding"]["x"]["field"] == "practice"
    assert spec["encoding"]["color"]["field"] == "budget"
    assert spec["encoding"]["color"]["scale"]["range"] == HEATMAP_COLOR_RANGE


def test_heatmap_uses_country_as_secondary_when_dimension_is_practice():
    data = [{"practice": "Risk Advisory", "country": "France", "budget": 1000}]
    spec = build_vega_spec(_base_intent(dimension="practice", chart_type="heatmap"), data)
    assert spec["encoding"]["y"]["field"] == "practice"
    assert spec["encoding"]["x"]["field"] == "country"


def test_heatmap_caps_to_top_countries_by_total_not_insertion_order():
    # 20 countries, each with one practice row — the weakest 5 must be dropped, and
    # the strongest (highest total budget) must survive, regardless of input order.
    data = [{"country": f"C{i}", "practice": "Risk Advisory", "budget": i * 1000} for i in range(20)]
    spec = build_vega_spec(_base_intent(dimension="country", chart_type="heatmap"), data)
    countries = {row["country"] for row in spec["data"]["values"]}
    assert len(countries) == MAX_HEATMAP_ROWS
    assert "C19" in countries  # highest budget must survive the cap
    assert "C0" not in countries  # lowest budget must be dropped


# ---------------------------------------------------------------------------
# funnel
# ---------------------------------------------------------------------------

def _funnel_data():
    # Deliberately out of pipeline order, and not sorted by value — the funnel must
    # reorder by stage, never by value (that would misrepresent a sales pipeline).
    return [
        {"status": "Offre gagnée", "nb_opportunities": 5},
        {"status": "Lead", "nb_opportunities": 40},
        {"status": "Offre perdue", "nb_opportunities": 12},  # exit, not a pipeline stage
        {"status": "NO GO", "nb_opportunities": 3},  # exit, not a pipeline stage
        {"status": "En cours de qualification", "nb_opportunities": 25},
    ]


def test_funnel_reorders_by_pipeline_stage_and_drops_exit_statuses():
    spec = build_vega_spec(
        _base_intent(dimension="status", metric="nb_opportunities", chart_type="funnel"),
        _funnel_data(),
    )
    bar_layer = spec["layer"][0]
    stages = [row["stage"] for row in spec["data"]["values"]]
    assert stages == ["Lead", "En cours de qualification", "Offre gagnée"]
    assert "Offre perdue" not in stages
    assert "NO GO" not in stages
    assert bar_layer["encoding"]["y"]["sort"] == stages


def test_funnel_geometry_is_symmetric_around_zero():
    spec = build_vega_spec(
        _base_intent(dimension="status", metric="nb_opportunities", chart_type="funnel"),
        [{"status": "Lead", "nb_opportunities": 40}],
    )
    row = spec["data"]["values"][0]
    assert row["x_start"] == -20.0
    assert row["x_end"] == 20.0


def test_funnel_with_no_known_pipeline_stage_returns_placeholder_not_empty_chart():
    spec = build_vega_spec(
        _base_intent(dimension="status", metric="nb_opportunities", chart_type="funnel"),
        [{"status": "Offre perdue", "nb_opportunities": 12}, {"status": "NO GO", "nb_opportunities": 3}],
    )
    assert "layer" not in spec
    assert spec["mark"]["type"] == "text"
