import yaml

from backend import dac_composer
from backend.dac_composer import _complementary_dimension, _pack_rows, compose_widgets, write_generated_dashboard
from backend.sql_builder import build_sql


def _intent(**overrides):
    base = {
        "goal": "Budget par pays", "metric": "budget", "dimension": "country",
        "chart_type": "bar", "filters": {}, "range_filters": {},
        "use_raw_table": False, "limit": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# sql_builder — le SQL est produit par du code, jamais par le LLM
# ---------------------------------------------------------------------------

def test_apostrophes_in_values_are_escaped():
    # Les vraies données en contiennent (« Côte d'Ivoire ») — sans doublement de
    # l'apostrophe la requête serait syntaxiquement cassée.
    sql = build_sql(_intent(filters={"country": "Côte d'Ivoire"}))
    assert "'Côte d''Ivoire'" in sql


def test_list_filter_becomes_in_clause():
    sql = build_sql(_intent(filters={"country": ["France", "Maroc"]}))
    assert "country IN ('France', 'Maroc')" in sql


def test_numeric_filter_is_not_quoted_as_text():
    sql = build_sql(_intent(filters={"deadline_year": "2026"}))
    assert "deadline_year = 2026" in sql


def test_between_range_filter():
    sql = build_sql(_intent(range_filters={"days_remaining": {"op": "between", "value": [0, 7]}},
                             chart_type="table", use_raw_table=True))
    assert "days_remaining BETWEEN 0 AND 7" in sql


def test_exclude_statuses_becomes_not_in():
    # Les exclusions demandées s'AJOUTENT à celle, par défaut, des affaires perdues :
    # on vérifie donc leur présence dans la clause, pas une chaîne exacte qui casserait
    # au moindre ajout à la règle métier.
    sql = build_sql(_intent(exclude_statuses=["Offre gagnée", "NO GO"]))
    assert "status NOT IN (" in sql
    assert "'Offre gagnée'" in sql
    assert "'NO GO'" in sql


def test_kpi_intent_without_dimension_selects_a_single_value():
    sql = build_sql(_intent(dimension="", chart_type="kpi_card"))
    assert "AS value" in sql
    assert "GROUP BY" not in sql


def test_funnel_orders_by_pipeline_stage_not_by_value():
    # Un entonnoir trié par volume ne raconterait rien du parcours réel : l'ordre
    # vient du rang de l'étape dans le pipeline (voir sql_builder.funnel_sql).
    sql = build_sql(_intent(dimension="status", chart_type="funnel"))
    assert "ORDER BY rang" in sql
    # « Offre perdue » n'est jamais une ÉTAPE du pipeline. Elle apparaît bien dans la
    # requête, mais uniquement dans la clause d'exclusion — d'où la vérification sur
    # le WHEN du CASE, qui énumère les étapes, plutôt que sur le texte entier.
    assert "WHEN 'Offre perdue'" not in sql


def test_unknown_metric_falls_back_instead_of_injecting_it():
    sql = build_sql(_intent(metric="; DROP TABLE opportunities; --"))
    assert "DROP" not in sql
    assert "SUM(budget)" in sql


def test_unknown_dimension_is_dropped_instead_of_injected():
    sql = build_sql(_intent(dimension="evil_column"))
    assert "evil_column" not in sql


# ---------------------------------------------------------------------------
# Composition multi-widgets
# ---------------------------------------------------------------------------

def test_dashboard_has_several_widgets():
    widgets = compose_widgets(_intent())
    assert len(widgets) >= 4


def test_every_widget_keeps_the_question_filters():
    # Tous les widgets doivent parler du même périmètre que la question, sinon le
    # dashboard mélangerait des chiffres qui ne se comparent pas.
    widgets = compose_widgets(_intent(filters={"practice": "Risk Advisory"}))
    for widget in widgets:
        assert "Risk Advisory" in widget["sql"]


def test_complementary_dimension_avoids_the_primary_one():
    assert _complementary_dimension(_intent(dimension="practice")) != "practice"


def test_complementary_dimension_avoids_a_dimension_pinned_by_a_filter():
    # Grouper par practice alors que la question filtre sur UNE practice donnerait
    # un graphique à une seule barre — aucune information.
    complement = _complementary_dimension(_intent(dimension="country", filters={"practice": "Risk Advisory"}))
    assert complement not in ("country", "practice")


def test_rows_never_exceed_the_twelve_column_grid():
    rows = _pack_rows(compose_widgets(_intent()))
    for row in rows:
        assert sum(w.get("col", 6) for w in row["widgets"]) <= 12


def test_table_question_still_produces_a_dashboard():
    widgets = compose_widgets(_intent(chart_type="table", use_raw_table=True))
    assert any(w["type"] == "table" for w in widgets)
    assert any(w["type"] == "metric" for w in widgets)


def test_funnel_question_does_not_duplicate_the_funnel():
    widgets = compose_widgets(_intent(dimension="status", chart_type="funnel"))
    funnels = [w for w in widgets if w.get("chart") == "funnel"]
    assert len(funnels) == 1


# ---------------------------------------------------------------------------
# Écriture du fichier YAML
# ---------------------------------------------------------------------------

def test_written_dashboard_is_valid_yaml_with_the_expected_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    name = write_generated_dashboard("budget par pays pour Risk Advisory",
                                      _intent(filters={"practice": "Risk Advisory"}))

    written = (tmp_path / dac_composer._generated_filename(name)).read_text(encoding="utf-8")
    parsed = yaml.safe_load(written)

    assert parsed["name"] == name
    assert parsed["connection"] == dac_composer.CONNECTION
    assert parsed["rows"]
    assert all("widgets" in row for row in parsed["rows"])


def test_sql_is_written_as_a_readable_literal_block(tmp_path, monkeypatch):
    # L'intérêt d'un dashboard « as code » est d'être relu en revue : le SQL doit
    # rester lisible tel quel, pas replié en style quoté par PyYAML.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    name = write_generated_dashboard("budget par pays", _intent())

    written = (tmp_path / dac_composer._generated_filename(name)).read_text(encoding="utf-8")
    assert "sql: |" in written


def test_dashboard_name_stays_url_safe_and_bounded():
    # Le nom est aussi la route DAC (/d/<nom>) : un caractère d'URL qui passerait
    # rendrait le dashboard inatteignable.
    name = dac_composer._dashboard_name("budget par pays ? / avec des #caractères% bizarres")
    for forbidden in ("/", "?", "#", "%"):
        assert forbidden not in name


def test_very_long_question_is_truncated():
    assert len(dac_composer._dashboard_name("budget " * 60)) <= 75


def test_a_written_dashboard_is_named_after_the_resolved_goal(tmp_path, monkeypatch):
    # « en camembert » est une retouche : elle ne décrit pas l'analyse produite.
    # C'est l'objectif résolu qui nomme le dashboard, sinon la liste des analyses
    # se remplirait d'intitulés muets.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    name = write_generated_dashboard("en camembert", _intent(goal="Budget par pays — Risk Advisory"))
    assert name.startswith("Budget par pays")


def test_the_working_dashboard_keeps_a_constant_name(tmp_path, monkeypatch):
    # Deux questions différentes doivent réécrire LE MÊME dashboard, donc conserver
    # la même route : c'est ce qui fait que l'affichage est modifié sur place au
    # lieu d'ouvrir un tableau de bord de plus.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    premier = dac_composer.write_main_dashboard("budget par pays", _intent())
    second = dac_composer.write_main_dashboard("budget par practice", _intent(dimension="practice"))

    assert premier == second == dac_composer.MAIN_DASHBOARD_NAME
    ecrits = list(tmp_path.glob("*.yml"))
    assert [f.name for f in ecrits] == [dac_composer.MAIN_FILENAME]


# ---------------------------------------------------------------------------
# Justesse des chiffres — vérifiée en exécutant le SQL sur des données de test,
# pas seulement en inspectant la chaîne générée.
# ---------------------------------------------------------------------------

import duckdb

from backend.dac_composer import _question_archetype, compose_widgets
from backend.sql_builder import funnel_sql


def _db_with(rows):
    """Base DuckDB en mémoire contenant une table opportunities minimale."""
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE opportunities (country VARCHAR, practice VARCHAR, status VARCHAR, "
        "budget DOUBLE, win_probability DOUBLE, weighted_amount DOUBLE, "
        "financial_offer DOUBLE, days_remaining INTEGER, deadline DATE, buyer VARCHAR)"
    )
    for r in rows:
        con.execute(
            "INSERT INTO opportunities VALUES (?, ?, ?, ?, NULL, NULL, NULL, 5, DATE '2026-12-31', 'ACME')",
            [r.get("country", "France"), r.get("practice", "Risk Advisory"),
             r.get("status", "Lead"), r.get("budget", 1000.0)],
        )
    return con


def test_funnel_is_cumulative_so_it_actually_decreases():
    # status est un état COURANT : compter les opportunités par statut ne décroît pas
    # forcément. Ici l'étape finale contient plus de lignes que la précédente — un
    # comptage brut dessinerait un "entonnoir" qui s'élargit.
    con = _db_with(
        [{"status": "Offre remise"}] * 7 + [{"status": "Offre gagnée"}] * 56
    )
    rows = con.execute(funnel_sql({"filters": {}, "range_filters": {}})).fetchall()
    valeurs = [n for _, n in rows]
    assert valeurs == sorted(valeurs, reverse=True), f"entonnoir non décroissant : {rows}"
    con.close()


def test_conversion_rate_never_exceeds_one_hundred_percent():
    # Régression : diviser deux comptages d'états courants donnait 56/7 = 800 %.
    # Le cumul « ayant atteint au moins cette étape » borne le taux à 100 %.
    con = _db_with(
        [{"status": "Offre remise"}] * 7 + [{"status": "Offre gagnée"}] * 56
    )
    rows = con.execute(funnel_sql({"filters": {}, "range_filters": {}}, conversion=True)).fetchall()
    taux = [t for _, t in rows if t is not None]
    assert taux, "aucun taux calculé"
    assert all(t <= 1.0 for t in taux), f"taux au-delà de 100 % : {rows}"
    con.close()


def test_capped_chart_still_totals_the_full_amount():
    # Régression : un LIMIT sec faisait disparaître les catégories en trop, et le
    # total du KPI ne correspondait plus à la somme des barres (6,58 M€ d'écart).
    rows = [{"country": f"Pays{i}", "budget": float(100 - i)} for i in range(20)]
    con = _db_with(rows)
    sql = build_sql(_intent(dimension="country", metric="budget", chart_type="bar"))
    affiche = sum(v for _, v, *_ in con.execute(sql).fetchall())
    total = con.execute("SELECT SUM(budget) FROM opportunities").fetchone()[0]
    assert affiche == total, f"{total - affiche} perdu silencieusement"
    con.close()


def test_capped_chart_groups_the_tail_under_autres():
    rows = [{"country": f"Pays{i}", "budget": float(100 - i)} for i in range(20)]
    con = _db_with(rows)
    labels = [r[0] for r in con.execute(build_sql(_intent(dimension="country"))).fetchall()]
    assert "Autres" in labels
    assert labels[-1] == "Autres", "« Autres » doit être en dernier, pas classé par valeur"
    con.close()


def test_user_requested_top_n_is_truncated_not_bucketed():
    # « top 5 » veut dire cinq lignes : y ajouter « Autres » trahirait la demande.
    rows = [{"country": f"Pays{i}", "budget": float(100 - i)} for i in range(20)]
    con = _db_with(rows)
    labels = [r[0] for r in con.execute(build_sql(_intent(dimension="country", limit=5))).fetchall()]
    assert len(labels) == 5
    assert "Autres" not in labels
    con.close()


# ---------------------------------------------------------------------------
# Pertinence : la composition dépend du type de question
# ---------------------------------------------------------------------------

def test_temporal_question_gets_no_funnel():
    # Un entonnoir de vente sous une courbe d'évolution ne répond à rien.
    widgets = compose_widgets(_intent(dimension="deadline_month", chart_type="line"))
    assert all(w.get("chart") != "funnel" for w in widgets)


def test_pipeline_question_gets_conversion_rates():
    widgets = compose_widgets(_intent(dimension="status", chart_type="funnel"))
    assert any("Taux de passage" in w["name"] for w in widgets)


def test_each_archetype_is_recognised():
    assert _question_archetype(_intent(dimension="deadline_month", chart_type="line")) == "temporal"
    assert _question_archetype(_intent(dimension="status", chart_type="funnel")) == "pipeline"
    assert _question_archetype(_intent(chart_type="scatter")) == "correlation"
    assert _question_archetype(_intent(chart_type="table", use_raw_table=True)) == "detail"
    assert _question_archetype(_intent(dimension="country", chart_type="bar")) == "breakdown"


def test_no_two_widgets_share_the_same_dimension():
    # Deux graphiques sur le même axe disent la même chose deux fois.
    widgets = compose_widgets(_intent(chart_type="table", use_raw_table=True, dimension=""))
    axes = [w["x"]["field"] for w in widgets if w.get("x")]
    assert len(axes) == len(set(axes)), f"dimension dupliquée : {axes}"


def test_each_question_keeps_its_own_dashboard_file(tmp_path, monkeypatch):
    # Régression : un fichier unique réécrit à chaque fois effaçait le dashboard de
    # la question précédente, rendant tout retour en arrière impossible.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    un = write_generated_dashboard("budget par pays", _intent())
    deux = write_generated_dashboard(
        "budget par practice", _intent(dimension="practice", goal="Budget par practice"))

    assert un != deux
    assert (tmp_path / dac_composer._generated_filename(un)).exists()
    assert (tmp_path / dac_composer._generated_filename(deux)).exists()


def test_two_phrasings_of_the_same_analysis_share_one_file(tmp_path, monkeypatch):
    # Le nom vient de l'analyse produite, pas de la phrase tapée : demander deux fois
    # la même chose autrement ne doit pas laisser deux fichiers identiques derrière
    # soi, ni deux entrées indiscernables dans la liste des analyses.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    un = write_generated_dashboard("budget par pays", _intent())
    deux = write_generated_dashboard("montre-moi le budget par pays", _intent())

    assert un == deux
    assert len(list(tmp_path.glob("*.yml"))) == 1


def test_old_generated_dashboards_are_pruned(tmp_path, monkeypatch):
    # Sans ménage, chaque question laisserait un fichier derrière elle indéfiniment.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    monkeypatch.setattr(dac_composer, "MAX_GENERATED_DASHBOARDS", 3)
    # Six analyses réellement DIFFÉRENTES — des axes distincts, pas seulement des
    # intitulés distincts. Le nom est reconstruit depuis l'intention validée (métrique,
    # axe, filtres) et non depuis le texte de `goal`, qui est rédigé par le modèle :
    # six `goal` différents pour la même analyse partagent volontairement un fichier.
    for dimension in ("country", "practice", "status", "opp_type", "funding_source",
                      "deadline_year"):
        write_generated_dashboard(f"budget par {dimension}", _intent(dimension=dimension))

    restants = list(tmp_path.glob(f"{dac_composer.GENERATED_PREFIX}*.yml"))
    assert len(restants) == 3


def test_asking_the_same_question_twice_reuses_one_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    write_generated_dashboard("budget par pays", _intent())
    write_generated_dashboard("budget par pays", _intent())
    assert len(list(tmp_path.glob(f"{dac_composer.GENERATED_PREFIX}*.yml"))) == 1


# ---------------------------------------------------------------------------
# « Ajoute … » complète le tableau de bord au lieu de le remplacer
# ---------------------------------------------------------------------------

def _widgets_du_principal(tmp_path):
    contenu = yaml.safe_load((tmp_path / dac_composer.MAIN_FILENAME).read_text(encoding="utf-8"))
    return [w for row in contenu["rows"] for w in row["widgets"]]


def test_there_is_nothing_to_complete_before_a_first_question(tmp_path, monkeypatch):
    # « ajoute … » en tout début de session n'a rien à compléter : l'appelant doit
    # pouvoir le voir et retomber sur une composition normale, plutôt que d'échouer.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    assert dac_composer.append_to_main_dashboard("ajoute le budget par pays", _intent()) == (None, False)


def test_appending_keeps_the_existing_widgets(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    dac_composer.write_main_dashboard("budget par pays", _intent())
    avant = _widgets_du_principal(tmp_path)

    nom, ajoute = dac_composer.append_to_main_dashboard(
        "ajoute le nombre par statut",
        _intent(metric="nb_opportunities", dimension="status", goal="Nombre par statut"))

    apres = _widgets_du_principal(tmp_path)
    assert nom == dac_composer.MAIN_DASHBOARD_NAME and ajoute is True
    assert len(apres) == len(avant) + 1
    assert [w["name"] for w in apres][:len(avant)] == [w["name"] for w in avant]


def test_appending_the_same_widget_twice_changes_nothing(tmp_path, monkeypatch):
    # Et le dit : annoncer un ajout qui n'a pas eu lieu vaudrait tout autant que de
    # ne rien dire du tout.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    dac_composer.write_main_dashboard("budget par pays", _intent())
    ajout = _intent(metric="nb_opportunities", dimension="status", goal="Nombre par statut")

    dac_composer.append_to_main_dashboard("ajoute le nombre par statut", ajout)
    compte = len(_widgets_du_principal(tmp_path))
    nom, ajoute = dac_composer.append_to_main_dashboard("ajoute le nombre par statut", ajout)

    assert (nom, ajoute) == (dac_composer.MAIN_DASHBOARD_NAME, False)
    assert len(_widgets_du_principal(tmp_path)) == compte


def test_a_dashboard_stops_growing_past_the_readable_limit(tmp_path, monkeypatch):
    # Sans plafond, ajouter sans fin produirait une page complète où l'on ne trouve
    # plus rien — l'inverse du but recherché.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    monkeypatch.setattr(dac_composer, "MAX_MAIN_WIDGETS", 9)
    dac_composer.write_main_dashboard("budget par pays", _intent())

    for i, dimension in enumerate(["status", "practice", "funding_source", "opp_type"]):
        dac_composer.append_to_main_dashboard(
            "ajoute", _intent(dimension=dimension, goal="Analyse %d" % i))

    assert len(_widgets_du_principal(tmp_path)) == 9


def test_the_working_dashboard_keeps_its_name_when_completed(tmp_path, monkeypatch):
    # C'est ce qui fait qu'un ajout se voit apparaître sur le tableau de bord affiché
    # plutôt que d'ouvrir une page de plus.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    dac_composer.write_main_dashboard("budget par pays", _intent())
    nom, _ = dac_composer.append_to_main_dashboard(
        "ajoute le nombre par statut", _intent(dimension="status", goal="Nombre par statut"))

    contenu = yaml.safe_load((tmp_path / dac_composer.MAIN_FILENAME).read_text(encoding="utf-8"))
    assert nom == contenu["name"] == dac_composer.MAIN_DASHBOARD_NAME


def test_l_ecriture_du_dashboard_ne_laisse_jamais_un_fichier_a_moitie(tmp_path, monkeypatch):
    """Deux questions posées en même temps visent le MÊME `_principal.yml`.

    `write_text` tronque avant de remplir : entre les deux, le fichier est vide ou
    incomplet — et DAC surveille ce dossier en rechargement direct, donc il peut le
    relire précisément à cet instant. L'écriture passe désormais par un fichier
    provisoire remplacé d'un seul tenant ; ce test hammer le cas.
    """
    import threading
    import time

    import yaml as _yaml

    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path / "dashboards")
    monkeypatch.setattr(dac_composer, "TEMP_DIR", tmp_path / "tmp")
    (tmp_path / "dashboards").mkdir()
    anomalies = []

    def ecrire(dimension):
        for _ in range(15):
            try:
                dac_composer.write_main_dashboard(f"budget par {dimension}",
                                                  _intent(dimension=dimension))
            except Exception as erreur:  # noqa: BLE001 - on veut voir TOUTE défaillance
                anomalies.append(f"écriture : {erreur!r}")

    def relire():
        """Un lecteur qui RELÂCHE le fichier entre deux lectures, comme DAC.

        Sans la pause, trois threads Python en boucle serrée gardent le fichier
        ouvert en permanence : sous Windows aucun remplacement ne peut alors
        aboutir, et le test mesurerait la contention artificielle qu'il crée
        lui-même plutôt que la propriété recherchée.
        """
        fichier = tmp_path / "dashboards" / dac_composer.MAIN_FILENAME
        for _ in range(120):
            time.sleep(0.001)
            if not fichier.exists():
                continue
            try:
                contenu = _yaml.safe_load(fichier.read_text(encoding="utf-8"))
            except (FileNotFoundError, PermissionError):
                # Le fichier a été remplacé entre le exists() et la lecture. Sous
                # Windows, un échange atomique en cours refuse l'ouverture au lieu
                # de servir l'ancienne version — c'est le signe que le mécanisme
                # fonctionne, pas une défaillance. Un vrai lecteur réessaie.
                continue
            except Exception as erreur:  # noqa: BLE001
                # TOUT le reste est la faute qu'on traque : un YAML malformé ne peut
                # venir que d'un fichier lu à moitié écrit.
                anomalies.append(f"lecture tronquée : {erreur!r}")
                continue
            if contenu is not None and "rows" not in contenu:
                anomalies.append("dashboard lu sans ses lignes")

    fils = ([threading.Thread(target=ecrire, args=(d,))
             for d in ("country", "practice", "status", "buyer")]
            + [threading.Thread(target=relire) for _ in range(3)])
    for f in fils:
        f.start()
    for f in fils:
        f.join()

    assert not anomalies, anomalies[:5]
    assert not list((tmp_path / "tmp").glob("*.tmp")), "un fichier provisoire est resté derrière"
    # L'invariant qui compte : DAC surveille le dossier des dashboards en rechargement
    # direct. Un fichier provisoire posé DEDANS y déclenchait deux événements par
    # écriture — la moitié du journal de DAC n'était plus que ce bruit.
    assert not list((tmp_path / "dashboards").glob("*.tmp")), (
        "un provisoire a été écrit dans le dossier surveillé par DAC"
    )


# ---------------------------------------------------------------------------
# Le périmètre de la question doit atteindre TOUS les widgets
# ---------------------------------------------------------------------------

def test_tous_les_widgets_portent_l_exclusion_demandee():
    """Cinq widgets sur huit l'ignoraient.

    `_kpi_intent` et `_variant_intent` recopiaient une liste FERMÉE de clés, qui
    n'avait pas suivi l'ajout de `exclude_filters`. Sur « budget par pays hors
    Tunisie », le tableau de bord affichait donc « Budget : 103 900 001 DT » —
    Tunisie comprise — juste à côté d'un graphique qui l'excluait. Deux chiffres
    contradictoires sur le même écran, pour la même question.
    """
    widgets = compose_widgets(_intent(exclude_filters={"country": ["Tunisie"]}))
    sans = [w["name"] for w in widgets
            if not ("NOT IN" in w["sql"] and "Tunisie" in w["sql"])]
    assert not sans, f"widgets sans l'exclusion : {sans}"


def test_aucun_libelle_moyen_ne_recouvre_une_somme():
    """Le libellé venait de l'intention, le calcul d'une copie amputée.

    `aggregation` manquait lui aussi à la liste des clés recopiées : deux widgets
    s'intitulaient « Budget moyen (DT) » au-dessus d'une SOMME, à côté d'un
    troisième, homonyme, qui affichait bien la moyenne.
    """
    widgets = compose_widgets(_intent(aggregation="avg"))
    menteurs = [w["name"] for w in widgets
                if "moyen" in w["name"].lower() and "AVG(budget)" not in w["sql"]]
    assert not menteurs, f"libellés démentis par leur calcul : {menteurs}"


def test_une_question_de_moyenne_n_affiche_pas_deux_fois_la_meme_moyenne():
    # Le KPI principal EST la moyenne : le widget d'appoint « ordre de grandeur »
    # faisait alors double emploi, sous un nom identique.
    noms = [w["name"] for w in compose_widgets(_intent(aggregation="avg"))]
    assert len(noms) == len(set(noms)), f"widgets en double : {noms}"


def test_toute_cle_de_perimetre_atteint_les_widgets_derives():
    """Le garde-fou contre la prochaine clé oubliée.

    Les deux défauts ci-dessus ont la MÊME cause : une liste de clés recopiées à la
    main, qui ne suit pas quand l'intention gagne un champ. Ce test échoue dès qu'une
    clé déclarée dans `_CLES_DE_PERIMETRE` cesse d'être propagée.
    """
    perimetre = {
        "filters": {"practice": "Risk Advisory"},
        "range_filters": {"budget": {"op": ">", "value": 1000}},
        "exclude_statuses": ["Offre gagnée"],
        "exclude_filters": {"country": ["Tunisie"]},
        "aggregation": "avg",
        "hot_deals": True,
    }
    assert set(perimetre) == set(dac_composer._CLES_DE_PERIMETRE), (
        "ce test doit couvrir chaque clé de périmètre déclarée"
    )

    intent = _intent(**perimetre)
    for constructeur in (lambda: dac_composer._kpi_intent(intent, "budget"),
                         lambda: dac_composer._variant_intent(intent)):
        derive = constructeur()
        for cle, valeur in perimetre.items():
            assert derive.get(cle) == valeur, f"{cle} perdue par {constructeur}"
