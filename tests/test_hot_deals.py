"""Les affaires chaudes, du critère métier jusqu'au tableau affiché.

Ce tableau est le seul bloc du dashboard rendu par l'application et non par Bruin
DAC — le tableau de DAC ne défile pas verticalement. Il passe donc par une fonction
Python (`business_rules.hot_deals`) là où les KPI passent par du SQL, et les deux
doivent compter exactement la même population : c'est ce que vérifie le dernier test
de ce fichier.
"""
from datetime import date

import pandas as pd
import pytest

from backend.business_rules import HOT_DEAL_MIN_PROBABILITY, hot_deals


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


def test_the_threshold_is_a_minimum_not_an_equality():
    # Le cœur du sujet : 90 % et 100 % sont des affaires chaudes. Les vraies données
    # ne contiennent aucune valeur entre 80 et 100 %, donc seules des lignes
    # fabriquées peuvent le prouver.
    chaudes = hot_deals(_df([
        {"buyer": "Certaine", "win_probability": 1.0},
        {"buyer": "Presque sûre", "win_probability": 0.9},
        {"buyer": "Au seuil", "win_probability": HOT_DEAL_MIN_PROBABILITY},
        {"buyer": "Juste en dessous", "win_probability": 0.79},
    ]))
    assert set(chaudes["buyer"]) == {"Certaine", "Presque sûre", "Au seuil"}


def test_the_status_plays_no_part():
    # Décision métier explicite : seule la probabilité décide. Une affaire déjà
    # gagnée est à 100 %, donc chaude elle aussi.
    chaudes = hot_deals(_df([
        {"buyer": "Gagnée", "status": "Offre gagnée", "win_probability": 1.0},
        {"buyer": "Signée", "status": "Offre signée", "win_probability": 1.0},
        {"buyer": "Amont", "status": "Lead", "win_probability": 1.0},
        {"buyer": "Remise", "status": "Offre remise", "win_probability": 0.8},
    ]))
    assert len(chaudes) == 4


def test_an_opportunity_without_a_probability_stays_out():
    # Les 63 offres perdues ont une pondération vide dans le Sheet : elles sortent
    # d'elles-mêmes, une comparaison avec une valeur absente étant toujours fausse.
    # Aucun filtre de statut n'est donc nécessaire pour les écarter.
    chaudes = hot_deals(_df([
        {"buyer": "Sans pondération", "status": "Offre perdue", "win_probability": None,
         "weighted_amount": None},
        {"buyer": "Avec pondération", "win_probability": 0.8},
    ]))
    assert list(chaudes["buyer"]) == ["Avec pondération"]


def test_the_biggest_expected_value_comes_first():
    # Le tableau est borné en hauteur et défile : la plus forte espérance doit se
    # lire sans avoir à faire défiler quoi que ce soit.
    chaudes = hot_deals(_df([
        {"buyer": "Moyenne", "weighted_amount": 500.0},
        {"buyer": "Grosse", "weighted_amount": 9000.0},
        {"buyer": "Petite", "weighted_amount": 10.0},
    ]))
    assert list(chaudes["buyer"]) == ["Grosse", "Moyenne", "Petite"]


def test_nothing_is_truncated():
    # Le tableau montre TOUTES les affaires chaudes. Un plafond ici les rendrait
    # inatteignables, molette ou pas — c'est précisément ce qui a été corrigé.
    assert len(hot_deals(_df([{"buyer": "C%02d" % i} for i in range(60)]))) == 60


def test_an_empty_dataframe_does_not_break_the_endpoint():
    vide = pd.DataFrame(columns=["win_probability", "weighted_amount"])
    assert len(hot_deals(vide)) == 0
    assert hot_deals(None) is None


def test_the_python_and_sql_definitions_count_the_same_population():
    """Le tableau passe par pandas, les KPI par du SQL : ils doivent s'accorder.

    Deux écritures d'un même critère finissent par diverger — ce projet en a déjà
    fait l'expérience trois fois. Le seuil est ici confronté aux deux chemins sur les
    mêmes lignes.
    """
    import re

    import duckdb
    import yaml

    from tests.test_accueil_dashboard import ACCUEIL, COLONNES, _sans_jinja

    lignes = [
        {"buyer": "A", "win_probability": 1.0, "status": "Offre gagnée"},
        {"buyer": "B", "win_probability": 0.8},
        {"buyer": "C", "win_probability": 0.79},
        {"buyer": "D", "win_probability": None, "weighted_amount": None},
    ]
    df = _df(lignes)

    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    # Conversion valeur par valeur : sur une colonne float, pandas recoerce un None
    # en NaN, et `where(notnull, None)` n'y change rien. Ce n'est pas cosmétique —
    # DuckDB évalue « NaN >= 0.8 » à VRAI, si bien qu'insérer des NaN ferait compter
    # les lignes sans pondération et inventerait une divergence que le vrai export
    # n'a pas (il écrit des NULL, voir test_the_export_writes_nulls_never_nans).
    def _valeur(v):
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else v

    for ligne in df.to_dict("records"):
        con.execute("INSERT INTO opportunities VALUES (%s)" % ", ".join("?" for _ in COLONNES),
                     [_valeur(ligne[nom]) for nom, _ in COLONNES])

    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    kpi = next(w for row in doc["rows"] for w in row["widgets"] if w["name"] == "Affaires chaudes")
    par_sql = con.execute(_sans_jinja(kpi["sql"])).fetchall()[0][0]

    assert par_sql == len(hot_deals(df)) == 2


def test_the_export_writes_nulls_never_nans(tmp_path, monkeypatch):
    """Garde-fou sur un piège silencieux de DuckDB.

    « NaN >= 0.8 » y vaut VRAI. Si l'export écrivait des NaN plutôt que des NULL pour
    une pondération absente, le KPI « Affaires chaudes » compterait les 170 lignes
    sans pondération sans qu'aucune requête n'échoue — le chiffre passerait de 105 à
    275 en silence.
    """
    import duckdb

    from backend import duckdb_export

    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "test.db")
    df = _df([
        {"buyer": "Renseignée", "win_probability": 0.8},
        {"buyer": "Absente", "win_probability": None, "weighted_amount": None},
    ])
    assert duckdb_export.export_dataframe(df)

    con = duckdb.connect(str(tmp_path / "test.db"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM opportunities WHERE isnan(win_probability)").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM opportunities WHERE win_probability IS NULL").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM opportunities WHERE win_probability >= 0.8").fetchone()[0] == 1
