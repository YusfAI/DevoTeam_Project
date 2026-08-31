from datetime import date

from backend.business_rules import (
    HOT_DEAL_MIN_PROBABILITY, PENDING_SUBMISSION, SUBMITTED_STATUSES, WON_STATUSES,
)
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
    # Le modèle a déjà résolu un filtre de statut ; l'indice déterministe sur la
    # practice doit s'y AJOUTER sans toucher à ce qu'il a fourni.
    #
    # « perdues » plutôt que « gagnées » : ce dernier est un terme MÉTIER que le code
    # élargit volontairement à WON_STATUSES (voir le test ci-dessous), ce qui ferait
    # échouer ce test-ci pour une raison qui n'est pas la sienne.
    llm_intent = {
        "goal": "Budget des offres perdues pour Risk Advisory",
        "metric": "budget",
        "dimension": "",
        "filters": {"status": "Offre perdue"},
        "range_filters": {},
        "chart_type": "kpi_card",
        "aggregation": "sum",
        "use_raw_table": False,
        "is_conversation": False,
        "limit": 0,
    }
    result = refine_intent("budget des offres perdues pour Risk Advisory", llm_intent)
    assert result["filters"]["status"] == "Offre perdue"
    assert result["filters"]["practice"] == "Risk Advisory"


def test_une_offre_signee_compte_parmi_les_offres_gagnees():
    """« Gagnée » est un terme métier, pas le seul statut du même nom.

    Une offre signée a d'abord été remportée : la signature vient après la victoire.
    C'est ce que dit la vue d'ensemble, dont le KPI « Gagnées » compte WON_STATUSES.
    Le chat, lui, ne retenait que le statut littéral — « combien d'offres gagnées ? »
    répondait 56 quand le tableau de bord juste à côté en affichait 88. Deux chiffres
    pour la même question selon l'endroit où on la pose.
    """
    resultat = refine_intent("combien d'offres gagnées ?",
                             _base_intent(metric="nb_opportunities",
                                          filters={"status": "Offre gagnée"}))
    assert sorted(resultat["filters"]["status"]) == sorted(WON_STATUSES)


def test_la_negation_prime_sur_le_terme_metier():
    # « offres NON gagnées » ne doit pas devenir un filtre positif élargi : la
    # négation est traitée en exclusion, et elle passe d'abord.
    resultat = refine_intent("budget des offres non gagnées",
                             _base_intent(filters={"status": "Offre gagnée"}))
    assert "status" not in resultat["filters"]
    assert "Offre gagnée" in resultat["exclude_statuses"]


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


# --- « Offre pondérée » / « affaire chaude » : deux noms, une seule définition ---
# DEUX critères réunis par un OU : déjà remise, OU probabilité >= 80 %. L'un suffit.
# La réunion ne peut pas s'écrire avec les filtres de l'intention, qui sont tous
# combinés par ET — d'où le drapeau `hot_deals`, que les deux moteurs traduisent
# depuis business_rules (hot_deal_sql / hot_deal_mask).

def test_offre_ponderee_applies_the_business_rule_filters():
    intent = _base_intent(chart_type="table", use_raw_table=True)
    result = refine_intent("liste des offres pondérées", intent)
    assert result["hot_deals"] is True
    # Ni filtre de statut ni borne de probabilité : posés EN PLUS du drapeau, ils
    # rétabliraient le ET que la réunion vient précisément de remplacer.
    assert "status" not in result["filters"]
    assert "win_probability" not in result.get("range_filters", {})


def test_offres_ponderees_plural_also_matches():
    intent = _base_intent(chart_type="kpi_card")
    result = refine_intent("combien d'opportunités pondérées avons-nous ?", intent)
    assert result["hot_deals"] is True


def test_offre_ponderee_applies_its_threshold_whatever_the_llm_guessed():
    # La définition métier fait autorité sur le seuil, quoi qu'ait proposé le modèle.
    # Et le statut qu'il a ajouté SANS que la question en parle est retiré : c'est un
    # vestige de l'ancienne définition, qui faisait répondre 7 opportunités ici et 105
    # à une formulation voisine de la même question.
    intent = _base_intent(chart_type="table", use_raw_table=True, filters={"status": "Lead"})
    result = refine_intent("liste des offres pondérées", intent)
    assert result["hot_deals"] is True
    assert "status" not in result["filters"]


def test_offre_ponderee_garde_le_statut_que_la_question_nomme():
    # L'inverse du test précédent, et la raison pour laquelle le retrait n'est pas
    # aveugle : quand la QUESTION nomme un statut, il restreint légitimement le
    # périmètre et doit survivre. Seule l'initiative du modèle est écartée.
    intent = _base_intent(chart_type="table", use_raw_table=True, filters={"status": "Offre gagnée"})
    result = refine_intent("liste des affaires chaudes gagnées", intent)
    assert result["hot_deals"] is True
    assert result["filters"]["status"] == "Offre gagnée"


def test_offre_ponderee_does_not_force_the_chart_type():
    # Per spec: the filter always applies, but the display type stays driven by the
    # rest of the question — never forced to table/kpi_card by this rule alone.
    intent = _base_intent(chart_type="bar", dimension="country")
    result = refine_intent("budget des offres pondérées par pays", intent)
    assert result["chart_type"] == "bar"
    assert result["hot_deals"] is True


def test_montant_pondere_does_not_trigger_the_weighted_offer_rule():
    # "montant pondéré" refers to the weighted_amount metric, not the business term —
    # neither "offre" nor "opportunité" appears near "pondéré" here.
    intent = _base_intent(metric="weighted_amount", dimension="country")
    result = refine_intent("montant pondéré par pays", intent)
    assert "status" not in result.get("filters", {})
    assert not result.get("hot_deals")


def test_budget_pondere_alone_does_not_trigger_the_weighted_offer_rule():
    intent = _base_intent(metric="weighted_amount")
    result = refine_intent("quel est le budget pondéré total", intent)
    assert "status" not in result.get("filters", {})
    assert not result.get("hot_deals")


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


# ---------------------------------------------------------------------------
# choose_chart_type — la forme demandée est confrontée à la forme des données
# ---------------------------------------------------------------------------

from backend import business_rules
from backend.business_rules import choose_chart_type


def _chart(monkeypatch, cardinalite=3, **overrides):
    """Intention minimale, avec une cardinalité imposée : les tests ne doivent pas
    dépendre du contenu réel du Google Sheet du jour."""
    monkeypatch.setattr(business_rules, "distinct_count", lambda *a, **k: cardinalite)
    intent = {"metric": "budget", "dimension": "country", "chart_type": "bar",
              "filters": {}, "limit": 0}
    intent.update(overrides)
    return choose_chart_type(intent)


def test_a_pie_survives_when_there_are_few_slices(monkeypatch):
    chart, raison = _chart(monkeypatch, cardinalite=3, chart_type="pie")
    assert chart == "pie"
    assert raison == ""


def test_a_pie_becomes_bars_when_there_are_too_many_slices(monkeypatch):
    # 19 pays : au-delà de six parts, deux angles voisins ne se comparent plus.
    chart, raison = _chart(monkeypatch, cardinalite=19, chart_type="pie")
    assert chart == "bar"
    assert "19" in raison


def test_a_pie_of_averages_becomes_bars(monkeypatch):
    # Une moyenne ne s'additionne pas : elle ne forme pas des parts d'un tout, et un
    # camembert la présenterait pourtant comme telle.
    chart, raison = _chart(monkeypatch, cardinalite=3, chart_type="pie",
                            metric="win_probability")
    assert chart == "bar"
    assert "moyenne" in raison


def test_a_pie_of_a_top_n_becomes_bars(monkeypatch):
    # Les parts d'un top 5 ne totalisent pas le portefeuille : le camembert
    # afficherait des pourcentages d'un tout qu'il ne montre pas.
    chart, raison = _chart(monkeypatch, cardinalite=3, chart_type="pie", limit=5)
    assert chart == "bar"
    assert "top 5" in raison


def test_a_curve_on_a_non_temporal_dimension_becomes_bars(monkeypatch):
    chart, raison = _chart(monkeypatch, chart_type="line", dimension="practice")
    assert chart == "bar"
    assert raison


def test_a_temporal_dimension_gets_a_curve(monkeypatch):
    chart, _ = _chart(monkeypatch, chart_type="bar", dimension="deadline_month")
    assert chart == "line"


def test_without_a_dimension_there_is_only_a_number(monkeypatch):
    chart, raison = _chart(monkeypatch, chart_type="bar", dimension="")
    assert chart == "kpi_card"
    assert raison


def test_a_kpi_on_a_question_with_an_axis_becomes_a_chart(monkeypatch):
    # Écraser en un seul chiffre la répartition que la question demande à voir.
    chart, _ = _chart(monkeypatch, chart_type="kpi_card", dimension="country")
    assert chart == "bar"


def test_explicitly_requested_forms_are_never_revised(monkeypatch):
    # table, funnel, scatter et heatmap répondent à un besoin précis et nommé :
    # les remplacer trahirait la question au lieu de l'améliorer.
    for demande in ("table", "funnel", "scatter", "heatmap"):
        chart, raison = _chart(monkeypatch, cardinalite=99, chart_type=demande)
        assert chart == demande
        assert raison == ""


# ---------------------------------------------------------------------------
# try_followup_parse — retoucher sans perdre le contexte, ni en inventer
# ---------------------------------------------------------------------------

from backend.intent_refiner import try_followup_parse

_PRECEDENT = {
    "goal": "Budget par pays — Risk Advisory", "metric": "budget", "dimension": "country",
    "filters": {"practice": "Risk Advisory"}, "range_filters": {}, "chart_type": "bar",
    "aggregation": "sum", "use_raw_table": False, "limit": 0,
}


def test_an_adjustment_keeps_everything_it_does_not_change():
    suite = try_followup_parse("top 5", _PRECEDENT)
    assert suite["limit"] == 5
    assert suite["metric"] == "budget"
    assert suite["dimension"] == "country"
    assert suite["filters"] == {"practice": "Risk Advisory"}


def test_changing_the_axis_drops_the_filter_that_pinned_it():
    # Grouper PAR practice alors qu'un filtre fige UNE practice donnerait un
    # graphique à une seule barre — le filtre fait double emploi avec l'axe.
    suite = try_followup_parse("par practice", _PRECEDENT)
    assert suite["dimension"] == "practice"
    assert "practice" not in suite["filters"]


def test_a_comparison_keeps_its_multi_value_filter():
    # « compare la France et le Maroc » veut précisément cet axe ET cette
    # restriction : la règle précédente ne doit pas s'y appliquer.
    precedent = dict(_PRECEDENT, dimension="practice",
                      filters={"country": ["France", "Maroc"]})
    suite = try_followup_parse("par pays", precedent)
    assert suite["filters"]["country"] == ["France", "Maroc"]


def test_an_unrecognised_word_cancels_the_whole_adjustment():
    # Le garde-fou central : hériter en silence du contexte alors qu'un mot n'a pas
    # été compris revient à répondre à une autre question que celle posée.
    assert try_followup_parse("budget par pays au Maroc", _PRECEDENT) is None


def test_a_request_that_adjusts_nothing_is_not_an_adjustment():
    assert try_followup_parse("bonjour", _PRECEDENT) is None


def test_nothing_is_inherited_when_there_is_no_previous_question():
    assert try_followup_parse("en camembert", None) is None


def test_the_title_follows_the_adjustment():
    # Garder l'ancien titre laisserait croire que la retouche n'a pas été prise en
    # compte ; reprendre la phrase tapée donnerait « Par practice » comme intitulé.
    suite = try_followup_parse("par practice", _PRECEDENT)
    assert suite["goal"] == "Budget par practice"


# ---------------------------------------------------------------------------
# « Offres remises » : un terme métier, pas le statut du même nom
# ---------------------------------------------------------------------------

def _intent_vierge(**overrides):
    base = {"goal": "", "metric": "nb_opportunities", "dimension": "", "filters": {},
            "range_filters": {}, "chart_type": "kpi_card", "aggregation": "count",
            "use_raw_table": False, "limit": 0}
    base.update(overrides)
    return base


def test_submitted_offers_cover_every_status_that_proves_a_deposit():
    # Le statut décrit l'état COURANT : une offre partie chez le client et gagnée
    # depuis n'est plus au statut « Offre remise ». Compter ce seul statut donnait 4
    # offres là où 57 avaient réellement été déposées.
    intent = refine_intent("combien d'offres remises", _intent_vierge())
    assert intent["filters"]["status"] == list(SUBMITTED_STATUSES)


def test_the_natural_phrasing_with_words_in_between_is_recognised():
    # « combien d'offres A-T-ON remises » : trois mots séparent les deux termes, dont
    # un que \w seul ne sait pas lire.
    intent = refine_intent("combien d'offres a-t-on remises", _intent_vierge())
    assert intent["filters"]["status"] == list(SUBMITTED_STATUSES)


def test_a_submitted_offer_that_was_lost_still_counts_as_submitted():
    # C'est ce qui rend la question « sur le total remis, combien de perdues ? »
    # répondable — et ce qui lève l'exclusion par défaut des affaires perdues,
    # puisque l'intention filtre elle-même sur le statut.
    assert "Offre perdue" in SUBMITTED_STATUSES
    intent = refine_intent("offres remises", _intent_vierge())
    assert "Offre perdue" in intent["filters"]["status"]


def test_weighted_offers_keep_their_own_narrower_meaning():
    # Règle plus spécifique et périmètre tout autre : elle ne doit pas être avalée
    # par celle des offres remises, dont elle partage pourtant le mot « offres ».
    intent = refine_intent("liste des offres pondérées", _intent_vierge())
    assert intent["hot_deals"] is True
    # Surtout pas le filtre des offres REMISES (SUBMITTED_STATUSES) : les deux règles
    # partagent le mot « offres » mais ne désignent pas le même périmètre.
    assert "status" not in intent["filters"]


def test_a_plain_status_question_is_untouched():
    intent = refine_intent("offres perdues", _intent_vierge())
    assert intent["filters"]["status"] == "Offre perdue"


def test_the_three_outcome_lists_partition_the_submitted_ones():
    # Les KPI « gagnées », « perdues » et « en attente » doivent additionner le total
    # des offres remises : un statut oublié dans une des listes ferait un dashboard
    # dont les parties ne font pas le tout.
    gagnees = set(WON_STATUSES)
    attente = set(PENDING_SUBMISSION)
    perdues = set(SUBMITTED_STATUSES) - gagnees - attente

    assert gagnees | attente | perdues == set(SUBMITTED_STATUSES)
    assert not (gagnees & attente) and not (gagnees & perdues) and not (attente & perdues)
    assert perdues == {"Offre perdue"}


# ---------------------------------------------------------------------------
# « Ajoute … » : compléter plutôt que remplacer
# ---------------------------------------------------------------------------

def test_an_add_verb_flags_the_intent_without_changing_the_analysis():
    # Le verbe pilote la façon dont le résultat rejoint l'écran, pas son contenu :
    # même métrique, même axe, mêmes filtres qu'une question sans le verbe.
    avec = refine_intent("ajoute le budget par pays", _intent_vierge(dimension="country"))
    sans = refine_intent("le budget par pays", _intent_vierge(dimension="country"))

    assert avec.get("append") is True
    assert not sans.get("append")
    for cle in ("metric", "dimension", "chart_type", "filters"):
        assert avec[cle] == sans[cle]


def test_an_add_verb_does_not_break_the_coverage_check():
    # Sans être reconnu comme mot d'application, « ajoute » resterait un mot non
    # compris et la retouche repartirait inutilement par le modèle.
    precedent = dict(_PRECEDENT, dimension="country")
    suite = try_followup_parse("ajoute par practice", precedent)
    assert suite is not None
    assert suite["dimension"] == "practice"
    assert suite.get("append") is not False


def test_a_status_named_complement_is_not_mistaken_for_an_add_verb():
    # « Complément d'information » est un statut du pipeline ; « compléter » un verbe
    # d'ajout. Les deux commencent pareil.
    intent = refine_intent("opportunités en complément d'information", _intent_vierge())
    assert not intent.get("append")


def test_la_negation_du_terme_metier_ecarte_les_deux_statuts_gagnants():
    """« Gagnées » et « non gagnées » doivent partitionner le portefeuille.

    Le terme positif couvre les deux statuts d'issue favorable ; sa négation n'en
    écartait qu'un, si bien que les offres signées comptaient dans les deux
    réponses. Les deux questions posées l'une après l'autre se contredisaient.
    """
    intent = refine_intent("combien d'offres n'ont pas été gagnées ?",
                           {"metric": "nb_opportunities", "filters": {}})

    assert sorted(intent["exclude_statuses"]) == sorted(WON_STATUSES)
    assert "status" not in intent.get("filters", {})
