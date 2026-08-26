"""Le critère des affaires chaudes, sur les deux chemins qui l'appliquent.

Le dashboard le traduit en SQL (widgets de accueil.yml), le chat en opération pandas
(intention → db_layer). Deux écritures d'un même critère finissent par diverger — ce
projet en a déjà fait l'expérience — d'où le test qui les confronte sur les mêmes
lignes.
"""
from datetime import date

import duckdb
import pandas as pd
import yaml

from backend import db_layer
from backend.business_rules import HOT_DEAL_MIN_PROBABILITY
from backend.intent_refiner import refine_intent
from tests.test_accueil_dashboard import ACCUEIL, COLONNES, _sans_jinja


def _opportunite(**champs):
    base = {
        "id": 1, "country": "France", "buyer": "Client", "description": "Mission",
        "practice": "Risk Advisory", "status": "Offre remise", "budget": 100000.0,
        "financial_offer": 90000.0, "win_probability": 0.8, "weighted_amount": 72000.0,
        "deadline": date(2026, 1, 15), "deadline_month": "2026-01",
        "deadline_year": 2026, "days_remaining": 30,
    }
    base.update(champs)
    return base


def _df(lignes):
    return pd.DataFrame([_opportunite(id=i + 1, **l) for i, l in enumerate(lignes)])


def _valeur(v):
    """None plutôt que NaN. Sur une colonne flottante pandas recoerce un None en NaN,
    et DuckDB évalue « NaN >= 0.8 » à VRAI : insérer des NaN inventerait une
    divergence que le vrai export n'a pas (voir test_the_export_writes_nulls…)."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _duckdb_avec(df):
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    for ligne in df.to_dict("records"):
        con.execute("INSERT INTO opportunities VALUES (%s)" % ", ".join("?" for _ in COLONNES),
                     [_valeur(ligne[nom]) for nom, _ in COLONNES])
    return con


def _widget(nom):
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    return next(w for row in doc["rows"] for w in row["widgets"] if w["name"] == nom)


def _kpi_affaires_chaudes(df):
    """Le compte tel que le dashboard l'affiche."""
    return _duckdb_avec(df).execute(_sans_jinja(_widget("Affaires chaudes")["sql"])).fetchall()[0][0]


def _compte_par_le_chat(df, monkeypatch):
    """Le même compte tel que le chat le calcule, en partant de la question posée."""
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)
    intention = refine_intent("combien d'affaires chaudes", {
        "goal": "", "metric": "nb_opportunities", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "count",
        "use_raw_table": False, "limit": 0,
    })
    return db_layer.build_and_execute_query(intention)[0]["nb_opportunities"]


def test_the_threshold_is_a_minimum_not_an_equality():
    # Le cœur du sujet : 90 % et 100 % sont des affaires chaudes. Les vraies données
    # ne contiennent aucune valeur entre 80 et 100 %, donc seules des lignes
    # fabriquées peuvent le prouver — remplacer « >= » par « = » ne changerait sinon
    # aucun chiffre affiché et passerait inaperçu.
    df = _df([
        {"buyer": "Certaine", "win_probability": 1.0},
        {"buyer": "Presque sûre", "win_probability": 0.9},
        {"buyer": "Au seuil", "win_probability": HOT_DEAL_MIN_PROBABILITY},
        {"buyer": "Juste en dessous", "win_probability": 0.79},
    ])
    assert _kpi_affaires_chaudes(df) == 3


def test_the_status_plays_no_part():
    # Décision métier explicite : seule la probabilité décide. Une affaire déjà
    # gagnée est à 100 %, donc chaude elle aussi.
    df = _df([
        {"buyer": "Gagnée", "status": "Offre gagnée", "win_probability": 1.0},
        {"buyer": "Amont", "status": "Lead", "win_probability": 1.0},
        {"buyer": "Remise", "status": "Offre remise", "win_probability": 0.8},
    ])
    assert _kpi_affaires_chaudes(df) == 3


def test_an_opportunity_without_a_probability_stays_out():
    # Les 63 offres perdues ont une pondération vide dans le Sheet : elles sortent
    # d'elles-mêmes, une comparaison avec une valeur absente étant toujours fausse.
    # Aucun filtre de statut n'est donc nécessaire pour les écarter.
    df = _df([
        {"buyer": "Sans pondération", "status": "Offre perdue", "win_probability": None,
         "weighted_amount": None},
        {"buyer": "Avec pondération", "win_probability": 0.8},
    ])
    assert _kpi_affaires_chaudes(df) == 1


def test_the_table_shows_every_hot_deal_biggest_first():
    # Aucune ligne n'est retirée : la liste entière est dans le dashboard, la plus
    # forte espérance de gain en tête. Un LIMIT rendrait les suivantes inatteignables.
    df = _df([{"buyer": "C%02d" % i, "weighted_amount": float(1000 - i)} for i in range(30)])

    lignes = _duckdb_avec(df).execute(
        _sans_jinja(_widget("Détail des affaires chaudes")["sql"])).fetchall()
    assert len(lignes) == 30
    assert [l[1] for l in lignes] == ["C%02d" % i for i in range(30)]


def test_the_detail_table_sits_alone_on_its_row():
    # Demandé explicitement, et pas seulement cosmétique : partagée, la ligne
    # imposerait sa hauteur au widget voisin, qui s'étirerait avec la liste.
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    ligne = next(r for r in doc["rows"]
                  if any(w["name"] == "Détail des affaires chaudes" for w in r["widgets"]))

    assert len(ligne["widgets"]) == 1
    assert ligne["widgets"][0]["col"] == 12
    # Aucune hauteur : le tableau de DAC ne défile pas verticalement, la borner
    # clipperait les affaires suivantes au lieu de les rendre atteignables.
    assert "height" not in ligne


def test_the_dashboard_and_the_chat_count_the_same_population(monkeypatch):
    df = _df([
        {"buyer": "A", "win_probability": 1.0, "status": "Offre gagnée"},
        {"buyer": "B", "win_probability": 0.8},
        {"buyer": "C", "win_probability": 0.79},
        {"buyer": "D", "win_probability": None, "weighted_amount": None},
    ])
    assert _kpi_affaires_chaudes(df) == _compte_par_le_chat(df, monkeypatch) == 2


def test_the_export_writes_nulls_never_nans(tmp_path, monkeypatch):
    """Garde-fou sur un piège silencieux de DuckDB.

    « NaN >= 0.8 » y vaut VRAI. Si l'export écrivait des NaN plutôt que des NULL pour
    une pondération absente, le KPI « Affaires chaudes » compterait les 170 lignes
    sans pondération sans qu'aucune requête n'échoue — le chiffre passerait de 105 à
    275 en silence.
    """
    from backend import duckdb_export

    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "test.db")
    df = _df([
        {"buyer": "Renseignée", "win_probability": 0.8},
        {"buyer": "Absente", "win_probability": None, "weighted_amount": None},
    ])
    assert duckdb_export.export_dataframe(df)

    con = duckdb.connect(str(tmp_path / "test.db"), read_only=True)
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE isnan(win_probability)").fetchone()[0] == 0
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE win_probability IS NULL").fetchone()[0] == 1
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE win_probability >= 0.8").fetchone()[0] == 1
