from backend.response_builder import format_metric_value, build_data_response, _describe_filters


def test_format_metric_value_none_is_na_not_zero():
    assert format_metric_value(None, "win_probability") == "N/A"
    assert format_metric_value(None, "weighted_amount") == "N/A"


def test_format_metric_value_units():
    assert format_metric_value(1234, "budget") == "1 234 €"
    assert format_metric_value(7, "nb_opportunities") == "7"


def test_win_probability_is_stored_as_fraction_and_displayed_as_percent():
    # win_probability is stored in DB as a 0-1 fraction (0.74 = 74%), never as
    # a ready-made percentage — must be scaled ×100, not printed raw.
    assert format_metric_value(0.738, "win_probability") == "73.8 %"
    assert format_metric_value(1.0, "win_probability") == "100.0 %"


def test_no_data_message():
    intent = {"metric": "budget", "filters": {}}
    assert build_data_response(intent, []).startswith("Aucune donnée trouvée")


def test_kpi_with_null_value_reports_na():
    intent = {"metric": "weighted_amount", "dimension": "", "chart_type": "kpi_card", "goal": "Montant pondéré"}
    message = build_data_response(intent, [{"weighted_amount": None}])
    assert "N/A" in message


def test_dimension_breakdown_excludes_null_rows_from_ranking():
    intent = {"metric": "budget", "dimension": "country", "chart_type": "bar", "goal": "Budget par pays"}
    data = [
        {"country": "France", "budget": 100},
        {"country": "Germany", "budget": None},
    ]
    message = build_data_response(intent, data)
    assert "France" in message
    assert "1 pays" in message


def test_list_valued_filter_is_rendered_readably_not_as_python_repr():
    intent = {"filters": {"country": ["France", "Maroc"]}, "range_filters": {}}
    desc = _describe_filters(intent)
    assert desc == " — filtres : pays = France, Maroc"
    assert "[" not in desc


def test_between_range_filter_is_rendered_readably():
    intent = {"filters": {}, "range_filters": {"deadline_month": {"op": "between", "value": ["2026-07", "2026-09"]}}}
    desc = _describe_filters(intent)
    assert "entre 2026-07 et 2026-09" in desc
