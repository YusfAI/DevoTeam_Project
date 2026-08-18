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
    # Un entonnoir trié par volume ne raconterait rien du parcours réel.
    sql = build_sql(_intent(dimension="status", chart_type="funnel"))
    assert "ORDER BY etape" in sql
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

    written = (tmp_path / dac_composer.GENERATED_FILENAME).read_text(encoding="utf-8")
    parsed = yaml.safe_load(written)

    assert parsed["name"] == name
    assert parsed["connection"] == dac_composer.CONNECTION
    assert parsed["rows"]
    assert all("widgets" in row for row in parsed["rows"])


def test_sql_is_written_as_a_readable_literal_block(tmp_path, monkeypatch):
    # L'intérêt d'un dashboard « as code » est d'être relu en revue : le SQL doit
    # rester lisible tel quel, pas replié en style quoté par PyYAML.
    monkeypatch.setattr(dac_composer, "DASHBOARDS_DIR", tmp_path)
    write_generated_dashboard("budget par pays", _intent())

    written = (tmp_path / dac_composer.GENERATED_FILENAME).read_text(encoding="utf-8")
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
