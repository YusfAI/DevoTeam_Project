from datetime import date

from backend.intent_refiner import try_rule_based_parse, refine_intent


def _base_intent(**overrides):
    intent = {
        "goal": "Test", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    intent.update(overrides)
    return intent


def test_greeting_is_conversational():
    result = try_rule_based_parse("bonjour")
    assert result["is_conversation"] is True
    assert result["metric"] == ""


def test_budget_by_country_high_confidence():
    result = try_rule_based_parse("budget par pays pour Risk Advisory")
    assert result is not None
    assert result["metric"] == "budget"
    assert result["dimension"] == "country"
    assert result["filters"]["practice"] == "Risk Advisory"
    assert result["chart_type"] == "bar"


def test_unrecognizable_query_returns_none():
    # No metric/dimension/practice/status/"top" signal at all -> rule-based parser
    # must bail out (return None) rather than guess, so the caller falls through to the LLM.
    assert try_rule_based_parse("xyz qwuiop asdf") is None


def test_urgent_list_forces_table():
    result = try_rule_based_parse("liste des opportunités qui expirent dans moins de 7 jours")
    assert result["use_raw_table"] is True
    assert result["chart_type"] == "table"
    assert result["range_filters"]["days_remaining"] == {"op": "<", "value": 7}


def test_refine_intent_backfills_filters_without_overriding():
    # LLM already resolved a status filter; the rule-based hint for "practice" should
    # be merged in without touching what the LLM already provided.
    llm_intent = {
        "goal": "Budget des offres gagnées pour Risk Advisory",
        "metric": "budget",
        "dimension": "",
        "filters": {"status": "Offre gagnée"},
        "range_filters": {},
        "chart_type": "kpi_card",
        "aggregation": "sum",
        "use_raw_table": False,
        "is_conversation": False,
        "limit": 0,
    }
    result = refine_intent("budget des offres gagnées pour Risk Advisory", llm_intent)
    assert result["filters"]["status"] == "Offre gagnée"
    assert result["filters"]["practice"] == "Risk Advisory"


def test_refine_intent_forces_pie_on_camembert_keyword():
    intent = {
        "metric": "nb_opportunities", "dimension": "practice", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    result = refine_intent("fais un camembert par practice", intent)
    assert result["chart_type"] == "pie"


# --- Dates et périodes relatives (déterministe, jamais calculées par le LLM) ---

def test_this_month():
    result = refine_intent("budget ce mois-ci", _base_intent(), today=date(2026, 8, 6))
    assert result["filters"]["deadline_month"] == "2026-08"


def test_last_month_crosses_year_boundary():
    result = refine_intent("budget le mois dernier", _base_intent(), today=date(2026, 1, 15))
    assert result["filters"]["deadline_month"] == "2025-12"


def test_this_year():
    result = refine_intent("budget cette année", _base_intent(), today=date(2026, 8, 6))
    assert result["filters"]["deadline_year"] == "2026"


def test_last_year():
    result = refine_intent("budget l'année dernière", _base_intent(), today=date(2026, 8, 6))
    assert result["filters"]["deadline_year"] == "2025"


def test_last_quarter_crosses_year_boundary():
    # February -> current quarter is Q1 2026, so "last quarter" is Q4 2025.
    result = refine_intent("budget le trimestre dernier", _base_intent(), today=date(2026, 2, 10))
    assert result["range_filters"]["deadline_month"] == {
        "op": "between", "value": ["2025-10", "2025-12"],
    }


def test_this_quarter():
    result = refine_intent("budget ce trimestre", _base_intent(), today=date(2026, 8, 6))
    assert result["range_filters"]["deadline_month"] == {
        "op": "between", "value": ["2026-07", "2026-09"],
    }


def test_last_n_months_crosses_year_boundary():
    result = refine_intent("budget les 6 derniers mois", _base_intent(), today=date(2026, 3, 10))
    assert result["range_filters"]["deadline_month"] == {
        "op": "between", "value": ["2025-09", "2026-03"],
    }


def test_relative_period_does_not_override_explicit_filter():
    # If the LLM already resolved an explicit deadline_month, the deterministic
    # relative-date pass must not clobber it.
    intent = _base_intent(filters={"deadline_month": "2020-01"})
    result = refine_intent("budget ce mois-ci", intent, today=date(2026, 8, 6))
    assert result["filters"]["deadline_month"] == "2020-01"


def test_no_relative_period_phrase_leaves_dates_untouched():
    result = refine_intent("budget par pays", _base_intent(dimension="country"), today=date(2026, 8, 6))
    assert "deadline_month" not in result["filters"]
    assert "deadline_year" not in result["filters"]
