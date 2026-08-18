from datetime import date

import pandas as pd
import pytest

from backend import db_layer


def _row(**overrides):
    base = dict(
        id=1, country="France", created_date=date(2026, 1, 1), deadline=date(2026, 9, 1),
        deadline_month="2026-09", deadline_year=2026, days_remaining=10,
        practice="Risk Advisory", description=None, buyer="ACME", opp_type="AO",
        status="Offre gagnée", budget=100000.0, funding_source="Fonds Propres",
        partner=None, financial_offer=90000.0, win_probability=0.8, weighted_amount=72000.0,
    )
    base.update(overrides)
    return base


@pytest.fixture
def fixture_df(monkeypatch):
    rows = [
        _row(id=1, country="France", practice="Risk Advisory", status="Offre gagnée",
             budget=100000.0, financial_offer=90000.0, win_probability=0.8, weighted_amount=72000.0,
             days_remaining=10, deadline_month="2026-09"),
        _row(id=2, country="France", practice="Data Management", status="Offre perdue",
             budget=50000.0, financial_offer=None, win_probability=None, weighted_amount=None,
             days_remaining=-5, deadline_month="2026-08"),
        _row(id=3, country="Maroc", practice="Risk Advisory", status="Lead",
             budget=200000.0, financial_offer=180000.0, win_probability=0.5, weighted_amount=90000.0,
             days_remaining=3, deadline_month="2026-08"),
    ]
    df = pd.DataFrame(rows)
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)
    return df


def test_dimension_grouping_sums_budget_by_default(fixture_df):
    intent = {"dimension": "country", "metric": "budget", "filters": {}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)

    by_country = {r["country"]: r["budget"] for r in result}
    assert by_country == {"France": 150000.0, "Maroc": 200000.0}


def test_nb_opportunities_metric_counts_rows(fixture_df):
    intent = {"dimension": "country", "metric": "nb_opportunities", "filters": {}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)

    by_country = {r["country"]: r["nb_opportunities"] for r in result}
    assert by_country == {"France": 2, "Maroc": 1}


def test_win_probability_metric_uses_mean_and_ignores_none(fixture_df):
    intent = {"dimension": "country", "metric": "win_probability", "filters": {}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)

    by_country = {r["country"]: r["win_probability"] for r in result}
    assert by_country["France"] == pytest.approx(0.8)  # seule la ligne id=1 a une valeur
    assert by_country["Maroc"] == pytest.approx(0.5)


def test_list_valued_filter_becomes_isin(fixture_df):
    intent = {
        "dimension": "country", "metric": "budget",
        "filters": {"country": ["France", "Maroc"]}, "range_filters": {},
    }
    result = db_layer.build_and_execute_query(intent)
    assert {r["country"] for r in result} == {"France", "Maroc"}


def test_scalar_filter_restricts_to_matching_rows(fixture_df):
    intent = {"dimension": "country", "metric": "budget", "filters": {"practice": "Risk Advisory"}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)
    assert {r["country"] for r in result} == {"France", "Maroc"}
    by_country = {r["country"]: r["budget"] for r in result}
    assert by_country == {"France": 100000.0, "Maroc": 200000.0}


def test_between_range_filter(fixture_df):
    intent = {
        "dimension": "", "metric": "budget", "filters": {},
        "range_filters": {"days_remaining": {"op": "between", "value": [0, 7]}},
        "use_raw_table": True,
    }
    result = db_layer.build_and_execute_query(intent)
    assert [r["days_remaining"] for r in result] == [3]


def test_exclude_statuses_removes_matching_rows(fixture_df):
    intent = {
        "dimension": "", "metric": "budget", "filters": {}, "range_filters": {},
        "use_raw_table": True, "exclude_statuses": ["Offre gagnée", "Offre perdue"],
    }
    result = db_layer.build_and_execute_query(intent)
    assert len(result) == 1
    assert result[0]["country"] == "Maroc"


def test_no_exclude_statuses_keeps_all_rows(fixture_df):
    intent = {"dimension": "", "metric": "budget", "filters": {}, "range_filters": {}, "use_raw_table": True}
    result = db_layer.build_and_execute_query(intent)
    assert len(result) == 3


def test_heatmap_groups_by_dimension_and_practice(fixture_df):
    intent = {"dimension": "country", "metric": "budget", "filters": {}, "range_filters": {}, "chart_type": "heatmap"}
    result = db_layer.build_and_execute_query(intent)
    keys = {(r["country"], r["practice"]) for r in result}
    assert ("France", "Risk Advisory") in keys
    assert ("France", "Data Management") in keys
    assert ("Maroc", "Risk Advisory") in keys


def test_heatmap_uses_country_as_secondary_when_dimension_is_practice(fixture_df):
    intent = {"dimension": "practice", "metric": "nb_opportunities", "filters": {}, "range_filters": {}, "chart_type": "heatmap"}
    result = db_layer.build_and_execute_query(intent)
    for r in result:
        assert "country" in r and "practice" in r


def test_scatter_forces_the_raw_per_opportunity_path_and_includes_weighted_amount(fixture_df):
    # Scatter needs several measures per opportunity (budget, win_probability,
    # weighted_amount) — never a single metric aggregated by a dimension.
    intent = {"dimension": "", "metric": "budget", "filters": {}, "range_filters": {}, "chart_type": "scatter"}
    result = db_layer.build_and_execute_query(intent)
    assert len(result) == 3
    assert "weighted_amount" in result[0]
    assert "win_probability" in result[0]


def test_no_dimension_returns_single_aggregated_value(fixture_df):
    intent = {"dimension": "", "metric": "budget", "filters": {}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)
    assert result == [{"budget": 350000.0}]


def test_deadline_month_dimension_sorts_ascending(fixture_df):
    intent = {"dimension": "deadline_month", "metric": "budget", "filters": {}, "range_filters": {}}
    result = db_layer.build_and_execute_query(intent)
    months = [r["deadline_month"] for r in result]
    assert months == sorted(months)


def test_limit_truncates_grouped_results(fixture_df):
    intent = {"dimension": "country", "metric": "budget", "filters": {}, "range_filters": {}, "limit": 1}
    result = db_layer.build_and_execute_query(intent)
    assert len(result) == 1
    assert result[0]["country"] == "Maroc"  # le plus gros budget, tri décroissant par défaut


def test_empty_dataframe_returns_empty_list(monkeypatch):
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: pd.DataFrame(columns=list(db_layer.RAW_TABLE_COLUMNS)))
    intent = {"dimension": "country", "metric": "budget", "filters": {}, "range_filters": {}}
    assert db_layer.build_and_execute_query(intent) == []
