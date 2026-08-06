from backend.vega_generator import build_vega_spec, MAX_BAR_CATEGORIES


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
