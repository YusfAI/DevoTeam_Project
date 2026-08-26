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
        _row(id=2, country="France", practice="Data Management", status="En cours de qualification",
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
        "use_raw_table": True, "exclude_statuses": ["Offre gagnée", "En cours de qualification"],
    }
    result = db_layer.build_and_execute_query(intent)
    assert len(result) == 1
    assert result[0]["country"] == "Maroc"


def test_open_statuses_are_all_kept_when_nothing_is_excluded(fixture_df):
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


# ---------------------------------------------------------------------------
# Exclusion par défaut des affaires perdues (règle métier)
# ---------------------------------------------------------------------------

from backend.business_rules import LOST_STATUSES


@pytest.fixture
def df_avec_perdues(monkeypatch):
    """Un gagné, un ouvert, et un de chaque statut d'échec."""
    rows = [
        _row(id=1, status="Offre gagnée", budget=100.0, country="France"),
        _row(id=2, status="Lead", budget=200.0, country="France"),
    ]
    for i, perdu in enumerate(LOST_STATUSES, start=3):
        rows.append(_row(id=i, status=perdu, budget=1000.0, country="France"))
    df = pd.DataFrame(rows)
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)
    return df


def test_lost_opportunities_are_excluded_from_totals(df_avec_perdues):
    # 5 statuts d'échec à 1000 chacun ne doivent pas gonfler le total : il ne reste
    # que le gagné (100) et l'ouvert (200).
    intent = {"dimension": "", "metric": "budget", "filters": {}, "range_filters": {}}
    assert db_layer.build_and_execute_query(intent)[0]["budget"] == 300.0


def test_won_opportunities_are_kept(df_avec_perdues):
    # Une affaire gagnée est un succès, pas une perte : elle reste comptée.
    intent = {"dimension": "", "metric": "nb_opportunities", "filters": {}, "range_filters": {}}
    assert db_layer.build_and_execute_query(intent)[0]["nb_opportunities"] == 2


def test_asking_explicitly_about_a_lost_status_still_returns_it(df_avec_perdues):
    # L'exclusion est un défaut, pas une censure : « liste des offres perdues » doit
    # répondre, sinon la donnée devient inatteignable.
    intent = {"dimension": "", "metric": "budget",
              "filters": {"status": "Offre perdue"}, "range_filters": {}}
    assert db_layer.build_and_execute_query(intent)[0]["budget"] == 1000.0


def test_every_lost_status_is_actually_excluded(df_avec_perdues):
    intent = {"dimension": "status", "metric": "budget", "filters": {}, "range_filters": {},
              "use_raw_table": True}
    statuts = {r["status"] for r in db_layer.build_and_execute_query(intent)}
    assert not (statuts & set(LOST_STATUSES)), f"statut perdu resté : {statuts}"


def test_pandas_and_sql_engines_agree_on_the_exclusion(df_avec_perdues):
    # Les deux moteurs doivent produire le même périmètre, sinon le message du chat
    # et les graphiques annonceraient deux totaux différents pour la même question.
    from backend.sql_builder import build_sql
    intent = {"dimension": "", "metric": "budget", "filters": {}, "range_filters": {},
              "chart_type": "kpi_card"}
    sql = build_sql(intent)
    for perdu in LOST_STATUSES:
        assert f"'{perdu}'" in sql, f"{perdu} absent de la clause SQL"


# ---------------------------------------------------------------------------
# Borner une valeur n'est pas demander une liste
# ---------------------------------------------------------------------------

def test_a_range_filter_alone_does_not_force_the_raw_row_path(fixture_df, monkeypatch):
    # Ce défaut a été trouvé trois fois, dans trois modules : db_layer, sql_builder et
    # response_builder traitaient (ou non) tout range_filter comme une demande de
    # liste. Résultat : « affaires chaudes par practice » renvoyait les lignes brutes
    # côté chat pendant que le dashboard groupait — deux réponses pour une question.
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: fixture_df)
    intent = {
        "metric": "nb_opportunities", "dimension": "practice", "chart_type": "bar",
        "filters": {}, "range_filters": {"win_probability": {"op": ">=", "value": 0.5}},
        "use_raw_table": False, "limit": 0,
    }
    result = db_layer.build_and_execute_query(intent)

    assert all("practice" in row and "nb_opportunities" in row for row in result)
    assert "buyer" not in result[0]  # une ligne brute en aurait un


def test_asking_for_a_list_still_gives_raw_rows(fixture_df, monkeypatch):
    # Le garde-fou de l'autre côté : c'est use_raw_table (ou chart_type == "table")
    # qui exprime le souhait d'une liste, et il doit continuer de fonctionner.
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: fixture_df)
    intent = {
        "metric": "budget", "dimension": "", "chart_type": "table",
        "filters": {}, "range_filters": {"days_remaining": {"op": "between", "value": [0, 7]}},
        "use_raw_table": True, "limit": 0,
    }
    result = db_layer.build_and_execute_query(intent)
    assert "buyer" in result[0]
