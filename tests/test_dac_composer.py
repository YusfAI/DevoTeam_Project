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
    sql = build_sql(_intent(exclude_statuses=["Offre gagnée", "NO GO"]))
    assert "status NOT IN ('Offre gagnée', 'NO GO')" in sql


def test_kpi_intent_without_dimension_selects_a_single_value():
    sql = build_sql(_intent(dimension="", chart_type="kpi_card"))
    assert "AS value" in sql
    assert "GROUP BY" not in sql


def test_funnel_orders_by_pipeline_stage_not_by_value():
    # Un entonnoir trié par volume ne raconterait rien du parcours réel : l'ordre
    # vient du rang de l'étape dans le pipeline (voir sql_builder.funnel_sql).
    sql = build_sql(_intent(dimension="status", chart_type="funnel"))
    assert "ORDER BY rang" in sql
    assert "'Offre perdue'" not in sql  # statut de sortie, jamais une étape


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


def test_dashboard_name_stays_url_safe_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    name = write_generated_dashboard("budget par pays ? / avec des #caractères% bizarres", _intent())

    for forbidden in ("/", "?", "#", "%"):
        assert forbidden not in name


def test_very_long_question_is_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    name = write_generated_dashboard("budget " * 60, _intent())
    assert len(name) <= 75


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
    deux = write_generated_dashboard("budget par practice", _intent(dimension="practice"))

    assert un != deux
    assert (tmp_path / dac_composer._generated_filename(un)).exists()
    assert (tmp_path / dac_composer._generated_filename(deux)).exists()


def test_old_generated_dashboards_are_pruned(tmp_path, monkeypatch):
    # Sans ménage, chaque question laisserait un fichier derrière elle indéfiniment.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    monkeypatch.setattr(dac_composer, "MAX_GENERATED_DASHBOARDS", 3)
    for i in range(6):
        write_generated_dashboard(f"question numero {i}", _intent())

    restants = list(tmp_path.glob(f"{dac_composer.GENERATED_PREFIX}*.yml"))
    assert len(restants) == 3


def test_asking_the_same_question_twice_reuses_one_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    write_generated_dashboard("budget par pays", _intent())
    write_generated_dashboard("budget par pays", _intent())
    assert len(list(tmp_path.glob(f"{dac_composer.GENERATED_PREFIX}*.yml"))) == 1
