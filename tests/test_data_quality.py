import pandas as pd

from backend import data_quality, data_store


def _summary(issues):
    return {"total_rows": 10, "skipped": len(issues), "errors": [], "issues": issues}


def test_value_belonging_to_another_column_is_diagnosed(monkeypatch):
    # « AMI » est un opp_type valide : le trouver dans status est une erreur de
    # colonne à la saisie, pas une valeur inconnue. Le dire fait gagner du temps.
    monkeypatch.setattr(data_quality, "get_last_refresh_summary",
                         lambda: _summary([{"row": 3, "field": "status", "value": "AMI", "message": "x"}]))
    rejet = data_quality.rejected_rows()[0]
    assert "opp_type" in rejet["diagnostic"]


def test_unknown_value_is_reported_without_inventing_a_cause(monkeypatch):
    monkeypatch.setattr(data_quality, "get_last_refresh_summary",
                         lambda: _summary([{"row": 5, "field": "status",
                                             "value": "En attente du plan de charge", "message": "x"}]))
    rejet = data_quality.rejected_rows()[0]
    assert "liste blanche" in rejet["diagnostic"]
    assert "opp_type" not in rejet["diagnostic"]


def test_identical_rejections_are_grouped_by_cause(monkeypatch):
    issues = [{"row": r, "field": "status", "value": "AMI", "message": "x"} for r in (3, 7, 9)]
    monkeypatch.setattr(data_quality, "get_last_refresh_summary", lambda: _summary(issues))
    rejets = data_quality.rejected_rows()
    assert len(rejets) == 1
    assert rejets[0]["nb_lignes"] == 3
    assert rejets[0]["lignes"] == [3, 7, 9]


def test_missing_values_are_reported_with_their_consequence(monkeypatch):
    df = pd.DataFrame({"win_probability": [0.5, None, None], "partner": ["A", "B", "C"]})
    monkeypatch.setattr(data_quality, "get_dataframe", lambda: df)
    manques = data_quality.missing_values()
    wp = next(m for m in manques if m["colonne"] == "win_probability")
    assert wp["nb_manquantes"] == 2
    assert wp["part"] == 2 / 3
    assert wp["consequence"]
    # Une colonne entièrement remplie ne doit pas polluer le rapport.
    assert all(m["colonne"] != "partner" for m in manques)


def test_quality_dataframe_has_the_columns_duckdb_expects(monkeypatch):
    monkeypatch.setattr(data_quality, "get_last_refresh_summary",
                         lambda: _summary([{"row": 3, "field": "status", "value": "AMI", "message": "x"}]))
    monkeypatch.setattr(data_quality, "get_dataframe",
                         lambda: pd.DataFrame({"win_probability": [None, 1.0]}))
    df = data_quality.quality_dataframe()
    assert list(df.columns) == ["categorie", "sujet", "nb", "part", "detail"]
    assert set(df["categorie"]) == {"Ligne rejetée", "Valeur manquante"}


def test_row_error_carries_the_field_and_value(monkeypatch):
    # C'est ce qui permet de regrouper par cause sans réanalyser les messages.
    try:
        data_store._normalize_choice("AMI", "status")
    except data_store.RowError as e:
        assert e.field == "status"
        assert e.value == "AMI"
    else:
        raise AssertionError("aurait dû lever RowError")
