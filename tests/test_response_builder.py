from backend.response_builder import format_metric_value, build_data_response, _describe_filters


def test_une_valeur_absente_se_dit_en_francais_pas_zero():
    # « N/A » est un sigle anglais dans une application francophone, et le même
    # utilisateur croisait par ailleurs « Non renseigné » — la valeur réellement
    # stockée quand une cellule du Sheet est vide. Une seule formulation, quelle que
    # soit la métrique. Et jamais zéro : une absence n'est pas une valeur nulle.
    for metrique in ("budget", "win_probability", "weighted_amount", "nb_opportunities"):
        assert format_metric_value(None, metrique) == "Non renseigné", metrique


def test_format_metric_value_units():
    # Les montants sont en dinars. L'unité vient de labels.DEVISE, partagée avec les
    # libellés des dashboards : deux écritures finiraient par diverger.
    assert format_metric_value(1234, "budget") == "1 234 DT"
    assert format_metric_value(7, "nb_opportunities") == "7"


def test_win_probability_is_stored_as_fraction_and_displayed_as_percent():
    # win_probability is stored in DB as a 0-1 fraction (0.74 = 74%), never as
    # a ready-made percentage — must be scaled ×100, not printed raw.
    # Virgule décimale : les milliers sont séparés à la française (« 103 900 001 DT »),
    # afficher « 73.8 % » dans la même phrase mélangeait deux conventions.
    assert format_metric_value(0.738, "win_probability") == "73,8 %"
    assert format_metric_value(1.0, "win_probability") == "100,0 %"


def test_no_data_message():
    intent = {"metric": "budget", "filters": {}}
    assert build_data_response(intent, []).startswith("Aucune donnée trouvée")


def test_un_kpi_sans_valeur_le_dit_en_toutes_lettres():
    # « Montant pondéré : N/A. » se lit comme une panne, pas comme un résultat. Et
    # quand un filtre est en cause, c'est LUI qu'il faut nommer : les autres formes
    # d'affichage le font déjà (« Aucune donnée trouvée — filtres : … »), le chiffre
    # unique était le seul à rester muet sur la raison.
    intent = {"metric": "weighted_amount", "dimension": "", "chart_type": "kpi_card",
              "goal": "Montant pondéré", "filters": {}, "range_filters": {}}
    message = build_data_response(intent, [{"weighted_amount": None}])
    assert "N/A" not in message
    assert "non renseigné" in message.lower()


def test_un_kpi_vide_a_cause_d_un_filtre_nomme_ce_filtre():
    intent = {"metric": "budget", "dimension": "", "chart_type": "kpi_card", "goal": "Budget",
              "filters": {"practice": "Data Management"}, "range_filters": {}}
    message = build_data_response(intent, [{"budget": None}])
    assert "Data Management" in message, "l'utilisateur doit savoir ce qui a vidé le périmètre"


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
    """Les mois se disent en toutes lettres, pas en code ISO.

    « 2026-07 » est la forme que la machine manipule ; personne ne la lit à voix
    haute. La phrase du chat s'adresse à un commercial, pas à un moteur de requête.
    """
    intent = {"filters": {}, "range_filters": {"deadline_month": {"op": "between", "value": ["2026-07", "2026-09"]}}}
    desc = _describe_filters(intent)
    assert "entre juillet 2026 et septembre 2026" in desc


def test_un_perimetre_metier_se_nomme_au_lieu_de_s_enumerer():
    """« Offres remises » vaut mieux que les cinq statuts et la borne qui la codent.

    La phrase disait COMMENT la question avait été traduite — « statut = Offre
    remise, En attente du plan de charge, Offre gagnée, Offre signée, Offre perdue,
    deadline <= 2026-08-31 » — quand l'utilisateur veut savoir CE QUI a été compté.
    """
    from backend.business_rules import SUBMITTED_STATUSES

    intent = {"filters": {"status": list(SUBMITTED_STATUSES)},
              "range_filters": {"deadline": {"op": "<=", "value": "2026-08-31"}}}
    desc = _describe_filters(intent)

    assert desc == " — filtres : offres remises"


def test_scatter_message_counts_plottable_rows_not_all_rows():
    intent = {"metric": "budget", "dimension": "", "chart_type": "scatter", "filters": {}, "range_filters": {}}
    data = [
        {"budget": 1000, "win_probability": 0.5},
        {"budget": 2000, "win_probability": None},  # not plottable, must not be counted
    ]
    message = build_data_response(intent, data)
    assert "1 opportunité" in message


def test_scatter_message_handles_no_plottable_rows_without_crashing():
    intent = {"metric": "budget", "dimension": "", "chart_type": "scatter", "filters": {}, "range_filters": {}}
    data = [{"budget": None, "win_probability": None}]
    message = build_data_response(intent, data)
    assert "Aucune opportunité" in message


def test_funnel_message_excludes_exit_statuses_not_shown_in_the_chart():
    # data includes every status the DB query returns (19), but the funnel chart only
    # plots pipeline stages — the text must match what's actually drawn, not the raw query.
    intent = {"metric": "nb_opportunities", "dimension": "status", "chart_type": "funnel",
              "goal": "Entonnoir de vente", "filters": {}, "range_filters": {}}
    data = [
        {"status": "Lead", "nb_opportunities": 32},
        {"status": "Offre gagnée", "nb_opportunities": 4},
        {"status": "Offre perdue", "nb_opportunities": 63},  # exit status, not a pipeline stage
        {"status": "NO GO", "nb_opportunities": 3},  # exit status, not a pipeline stage
    ]
    message = build_data_response(intent, data)
    assert "Offre perdue" not in message
    assert "NO GO" not in message
    assert "2 étape" in message


def test_heatmap_message_dit_le_vrai_total_et_ce_que_la_carte_omet():
    # 20 pays, dont la carte ne garde que les 15 plus forts (business_rules
    # MAX_HEATMAP_ROWS). Le message annonçait alors « Total » pour la somme des
    # SEULES cases affichées : sur les vraies données, 103 340 001 DT là où le
    # portefeuille en pèse 103 900 001 — quatre pays soustraits en silence sous une
    # étiquette qui promettait l'exhaustivité.
    #
    # Il doit désormais faire les deux : donner le vrai total, ET dire ce que la
    # carte laisse de côté. Taire l'un ou l'autre est une façon différente de mentir.
    intent = {"metric": "budget", "dimension": "country", "chart_type": "heatmap",
              "filters": {}, "range_filters": {}}
    data = [{"country": f"C{i}", "practice": "Risk Advisory", "budget": i * 1000} for i in range(20)]
    message = build_data_response(intent, data)

    total_reel = sum(r["budget"] for r in data)
    assert f"{total_reel:,.0f}".replace(",", " ") in message, "le total annoncé n'est pas le vrai total"
    assert "20 pays" in message, "le nombre réel de pays doit être dit"
    assert "15" in message, "la limite d'affichage doit être dite"
    assert "n'y figurent pas" in message, "l'omission doit être nommée, pas déduite"


def test_heatmap_message_sums_by_dimension_not_by_grid_cell():
    # Two cells share the same country (France) — the reported total must be the
    # true sum across both cells, not just whichever cell happened to sort first.
    intent = {"metric": "budget", "dimension": "country", "chart_type": "heatmap", "filters": {}, "range_filters": {}}
    data = [
        {"country": "France", "practice": "Risk Advisory", "budget": 100},
        {"country": "France", "practice": "Data Management", "budget": 50},
        {"country": "Maroc", "practice": "Risk Advisory", "budget": 80},
    ]
    message = build_data_response(intent, data)
    assert "230" in message  # 100 + 50 + 80
    assert "2 pays" in message


# ---------------------------------------------------------------------------
# Note de concentration — dire ce qui est notable, pas seulement le classement
# ---------------------------------------------------------------------------

from backend.response_builder import _concentration_note


def test_concentration_is_flagged_when_a_few_values_hold_the_total():
    rows = [("A", 50.0), ("B", 30.0), ("C", 15.0), ("D", 3.0), ("E", 2.0)]
    note = _concentration_note(rows, 100.0, "pays")
    assert "95 %" in note


def test_balanced_distribution_gets_no_note():
    # Commenter une répartition ordinaire noierait l'information utile.
    rows = [("A", 20.0)] * 5
    assert _concentration_note(rows, 100.0, "pays") == ""


def test_too_few_values_gets_no_note():
    # Sur trois catégories, « les 3 premières font 100 % » n'apprend rien.
    rows = [("A", 60.0), ("B", 30.0), ("C", 10.0)]
    assert _concentration_note(rows, 100.0, "practice") == ""


def test_zero_total_is_not_divided_by():
    assert _concentration_note([("A", 0.0)] * 6, 0.0, "pays") == ""


def test_uniform_spread_is_never_called_concentration_whatever_the_count():
    # Régression : le seuil fixe de 60 % qualifiait de « concentration » une
    # répartition parfaitement égale sur 5 catégories (3/5 = 60 % par construction).
    for n in (5, 6, 8, 12, 21):
        rows = [(f"V{i}", 100.0 / n) for i in range(n)]
        assert _concentration_note(rows, 100.0, "pays") == "", f"faux positif à n={n}"


def test_plural_does_not_double_an_existing_s():
    # « pays » est invariable : le suffixer donnait « payss ».
    rows = [("A", 90.0)] + [(f"V{i}", 1.0) for i in range(10)]
    assert "payss" not in _concentration_note(rows, 100.0, "pays")
    assert "pays" in _concentration_note(rows, 100.0, "pays")
    # Un label normal reste accordé.
    assert "practices" in _concentration_note(rows, 100.0, "practice")


# ---------------------------------------------------------------------------
# describe_change — dire ce qui a changé dans le tableau de bord
# ---------------------------------------------------------------------------

from backend.response_builder import describe_change, list_changes

_AVANT = {"metric": "budget", "dimension": "country", "chart_type": "bar",
          "filters": {"practice": "Risk Advisory"}, "limit": 0}


def test_a_change_of_display_is_named():
    phrase = describe_change(_AVANT, dict(_AVANT, chart_type="pie"))
    assert "barres → camembert" in phrase


def test_a_change_of_axis_is_named():
    phrase = describe_change(_AVANT, dict(_AVANT, dimension="practice"))
    assert "pays → practice" in phrase


def test_removing_the_filters_is_named():
    assert "filtres retirés" in describe_change(_AVANT, dict(_AVANT, filters={}))


def test_an_unchanged_request_produces_no_sentence():
    # Distinct du cas « trop de changements » : la liste vide dit qu'il ne s'est
    # rien passé, ce que l'appelant transforme en message explicite.
    assert list_changes(_AVANT, dict(_AVANT)) == []
    assert describe_change(_AVANT, dict(_AVANT)) == ""


def test_a_wholly_different_analysis_is_not_called_a_modification():
    # Énumérer cinq différences serait plus long que la réponse, et le mot
    # « modifié » deviendrait trompeur : ce n'est plus la même analyse.
    autre = {"metric": "nb_opportunities", "dimension": "status", "chart_type": "funnel",
             "filters": {}, "limit": 10}
    assert len(list_changes(_AVANT, autre)) > 3
    assert describe_change(_AVANT, autre) == ""


def test_no_previous_question_means_nothing_to_compare():
    assert describe_change(None, _AVANT) == ""


def test_a_bounded_value_is_not_a_request_for_a_list():
    # « combien d'affaires chaudes ? » répondait « 1 opportunité » : le nombre de
    # LIGNES du résultat agrégé, au lieu des 14 qu'il contenait. La cause était la
    # même qu'ailleurs — traiter tout range_filter comme une demande de liste.
    intent = {
        "metric": "nb_opportunities", "dimension": "", "chart_type": "kpi_card",
        "filters": {}, "range_filters": {"win_probability": {"op": ">=", "value": 0.8}},
        "use_raw_table": False, "limit": 0, "goal": "Affaires chaudes",
    }
    message = build_data_response(intent, [{"nb_opportunities": 14}])
    assert "14" in message
    assert "1 opportunité" not in message


def test_l_intitule_ne_repete_pas_la_phrase_qui_le_suit():
    """« Budget par pays — Budget par pays. Total : … » disait deux fois la même chose.

    Le titre est désormais reconstruit depuis l'intention validée : il coïncide donc
    très souvent avec l'en-tête de la phrase, et le préfixe n'apportait plus rien.
    """
    intent = {"metric": "budget", "dimension": "country", "chart_type": "bar",
              "filters": {}, "range_filters": {}, "goal": "Budget par pays"}
    message = build_data_response(intent, [{"country": "Tunisie", "budget": 100}])
    assert not message.startswith("Budget par pays — Budget par pays")


def test_mais_un_intitule_qui_apporte_quelque_chose_est_conserve():
    intent = {"metric": "budget", "dimension": "country", "chart_type": "bar",
              "filters": {}, "range_filters": {},
              "exclude_filters": {"country": ["Tunisie"]},
              "goal": "Budget par pays hors Tunisie"}
    message = build_data_response(intent, [{"country": "France", "budget": 100}])
    assert message.startswith("Budget par pays hors Tunisie — ")
