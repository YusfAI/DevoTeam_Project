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
    # "moins de 7 jours" veut dire une échéance À VENIR — jamais déjà passée
    # (days_remaining négatif) — donc borné à [0, 7], pas juste "< 7".
    assert result["range_filters"]["days_remaining"] == {"op": "between", "value": [0, 7]}


def test_refine_intent_normalizes_a_raw_lt_days_remaining_filter_from_the_llm():
    # Defensive guard: even if the LLM ignores the prompt instruction and emits a bare
    # "<" on days_remaining, refine_intent must still exclude already-expired deadlines.
    intent = _base_intent(
        metric="budget", dimension="", chart_type="table", use_raw_table=True,
        range_filters={"days_remaining": {"op": "<", "value": 10}},
    )
    result = refine_intent("opportunités urgentes", intent)
    assert result["range_filters"]["days_remaining"] == {"op": "between", "value": [0, 10]}


def test_refine_intent_normalizes_lte_days_remaining_too():
    intent = _base_intent(
        metric="budget", dimension="", chart_type="table", use_raw_table=True,
        range_filters={"days_remaining": {"op": "<=", "value": 5}},
    )
    result = refine_intent("opportunités urgentes", intent)
    assert result["range_filters"]["days_remaining"] == {"op": "between", "value": [0, 5]}


def test_refine_intent_leaves_other_range_filters_untouched():
    intent = _base_intent(
        metric="budget", dimension="", chart_type="table", use_raw_table=True,
        range_filters={"budget": {"op": "<", "value": 100000}},
    )
    result = refine_intent("opportunités sous 100000", intent)
    assert result["range_filters"]["budget"] == {"op": "<", "value": 100000}


def test_refine_intent_excludes_closed_statuses_for_any_days_remaining_query():
    # Consistent with backend/alerts.py's email digest: a closed deal is never
    # "urgent", even if its deadline technically falls in the requested window.
    intent = _base_intent(
        metric="budget", dimension="", chart_type="table", use_raw_table=True,
        range_filters={"days_remaining": {"op": "between", "value": [0, 7]}},
    )
    result = refine_intent("opportunités urgentes", intent)
    assert "Offre gagnée" in result["exclude_statuses"]
    assert "Offre perdue" in result["exclude_statuses"]


def test_refine_intent_does_not_set_exclude_statuses_without_a_days_remaining_filter():
    intent = _base_intent(
        metric="budget", dimension="", chart_type="table", use_raw_table=True,
        range_filters={"budget": {"op": "<", "value": 100000}},
    )
    result = refine_intent("opportunités sous 100000", intent)
    assert "exclude_statuses" not in result


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


def test_refine_intent_forces_status_dimension_for_funnel():
    # A funnel only ever makes sense on the pipeline status — forced deterministically
    # rather than trusting the LLM to set dimension="status" correctly every time.
    intent = _base_intent(chart_type="funnel", dimension="country", metric="nb_opportunities")
    result = refine_intent("montre-moi l'entonnoir de vente", intent)
    assert result["dimension"] == "status"


def test_refine_intent_defaults_heatmap_dimension_to_country_when_missing():
    intent = _base_intent(chart_type="heatmap", dimension="", metric="budget")
    result = refine_intent("carte de chaleur du budget", intent)
    assert result["dimension"] == "country"


def test_refine_intent_does_not_override_an_explicit_heatmap_dimension():
    intent = _base_intent(chart_type="heatmap", dimension="status", metric="budget")
    result = refine_intent("carte de chaleur du budget par statut", intent)
    assert result["dimension"] == "status"


def test_refine_intent_forces_budget_metric_for_scatter():
    # Prevents the win_probability x100 rescale (meant for a single aggregated
    # percentage) from corrupting the raw fraction used as the scatter's y-axis.
    intent = _base_intent(chart_type="scatter", dimension="", metric="win_probability")
    result = refine_intent("lien entre budget et probabilité de gain", intent)
    assert result["metric"] == "budget"


def test_rule_based_parser_detects_funnel_scatter_heatmap_area_keywords():
    assert try_rule_based_parse("montre le nombre d'opportunités en entonnoir")["chart_type"] == "funnel"
    assert try_rule_based_parse("budget en nuage de points")["chart_type"] == "scatter"
    assert try_rule_based_parse("budget en carte de chaleur")["chart_type"] == "heatmap"
    assert try_rule_based_parse("budget en aire par mois")["chart_type"] == "area"


def test_correlation_phrasing_without_the_literal_word_scatter_still_routes_to_scatter():
    # Regression: "lien entre X et Y" was previously caught by the metric-only fast
    # path (win_probability detected, no dimension -> silently defaulted to kpi_card,
    # which answers a completely different question than what was asked).
    result = try_rule_based_parse("y a-t-il un lien entre le budget et la probabilite de gain")
    assert result["chart_type"] == "scatter"


def test_area_keyword_does_not_false_positive_on_faire_or_affaire():
    # "aire" as a bare substring would wrongly match inside "faire"/"affaire" —
    # must require a word boundary.
    result = try_rule_based_parse("peux-tu me faire le budget par pays")
    assert result["chart_type"] != "area"


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


# --- "Offre pondérée" : win_probability >= 0.8 ET statut "Offre remise" ---

def test_offre_ponderee_applies_the_business_rule_filters():
    intent = _base_intent(chart_type="table", use_raw_table=True)
    result = refine_intent("liste des offres pondérées", intent)
    assert result["filters"]["status"] == "Offre remise"
    assert result["range_filters"]["win_probability"] == {"op": ">=", "value": 0.8}


def test_offres_ponderees_plural_also_matches():
    intent = _base_intent(chart_type="kpi_card")
    result = refine_intent("combien d'opportunités pondérées avons-nous ?", intent)
    assert result["filters"]["status"] == "Offre remise"
    assert result["range_filters"]["win_probability"] == {"op": ">=", "value": 0.8}


def test_offre_ponderee_overrides_a_weaker_llm_guess():
    # The business definition is authoritative: even if the LLM already set a
    # different status, "offre pondérée" must still win.
    intent = _base_intent(chart_type="table", use_raw_table=True, filters={"status": "Lead"})
    result = refine_intent("liste des offres pondérées", intent)
    assert result["filters"]["status"] == "Offre remise"


def test_offre_ponderee_does_not_force_the_chart_type():
    # Per spec: the filter always applies, but the display type stays driven by the
    # rest of the question — never forced to table/kpi_card by this rule alone.
    intent = _base_intent(chart_type="bar", dimension="country")
    result = refine_intent("budget des offres pondérées par pays", intent)
    assert result["chart_type"] == "bar"
    assert result["filters"]["status"] == "Offre remise"


def test_montant_pondere_does_not_trigger_the_weighted_offer_rule():
    # "montant pondéré" refers to the weighted_amount metric, not the business term —
    # neither "offre" nor "opportunité" appears near "pondéré" here.
    intent = _base_intent(metric="weighted_amount", dimension="country")
    result = refine_intent("montant pondéré par pays", intent)
    assert "status" not in result.get("filters", {})
    assert "win_probability" not in result.get("range_filters", {})


def test_budget_pondere_alone_does_not_trigger_the_weighted_offer_rule():
    intent = _base_intent(metric="weighted_amount")
    result = refine_intent("quel est le budget pondéré total", intent)
    assert "status" not in result.get("filters", {})
    assert "win_probability" not in result.get("range_filters", {})


# --- Choix du type de graphique ---

def test_evolution_forces_line_only_on_a_temporal_dimension():
    intent = _base_intent(chart_type="bar", dimension="deadline_month")
    result = refine_intent("évolution du budget par mois", intent)
    assert result["chart_type"] == "line"


def test_evolution_keyword_alone_does_not_force_line_on_country():
    result = try_rule_based_parse("évolution du budget par pays")
    assert result["dimension"] == "country"
    assert result["chart_type"] != "line"


def test_pourcentage_keyword_triggers_pie():
    result = try_rule_based_parse("quel pourcentage du budget par pays")
    assert result["dimension"] == "country"
    assert result["chart_type"] == "pie"


def test_proportion_keyword_triggers_pie_via_refine_intent():
    intent = _base_intent(chart_type="bar", dimension="practice")
    result = refine_intent("quelle proportion du budget par practice", intent)
    assert result["chart_type"] == "pie"
