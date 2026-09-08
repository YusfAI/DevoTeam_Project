"""L'export vers DuckDB ne doit jamais changer le TYPE d'une colonne temporelle.

Constaté sur un poste réel : la feuille de l'utilisatrice avait une colonne
« deadline » dans un format que `_parse_date` ne reconnaît pas — chaque ligne
échouait donc à sa lecture, et `deadline` valait None partout dans le DataFrame.

DuckDB devine le type d'une colonne pandas depuis les valeurs qu'elle contient.
Une colonne entièrement à None ne lui laisse rien à examiner, et il retombe sur
INTEGER au lieu de DATE. Chaque requête qui compare ensuite `deadline` à une date —
la quasi-totalité des widgets du tableau de bord — échouait alors avec :

    Binder Error: Cannot compare values of type INTEGER and type DATE

alors que le DataFrame pandas, source de vérité pour le chat, n'avait jamais eu le
moindre problème : `deadline` y vaut simplement None, une valeur que pandas comme
le reste de l'application savent déjà traiter. Le défaut n'existait que dans cette
projection.
"""
import duckdb

from backend import duckdb_export
from tests.test_hot_deals import _df


def test_une_colonne_deadline_entierement_vide_reste_comparable_a_une_date(
        tmp_path, monkeypatch):
    """Le cas réel : toutes les échéances de la feuille sont illisibles."""
    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "test.db")

    df = _df([
        {"deadline": None, "status": "Offre remise"},
        {"deadline": None, "status": "Offre gagnée"},
    ])
    assert duckdb_export.export_dataframe(df)

    con = duckdb.connect(str(tmp_path / "test.db"), read_only=True)
    type_deadline = [t for nom, t, *_ in con.execute("DESCRIBE opportunities").fetchall()
                     if nom == "deadline"][0]
    assert type_deadline not in ("INTEGER", "BIGINT"), (
        "« deadline » a perdu son type temporel : toute comparaison à une date "
        "échouerait avec une Binder Error, exactement la panne constatée.")

    # La requête qui plantait réellement, reprise du tableau de bord.
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE deadline <= CURRENT_DATE"
    ).fetchall() == [(0,)]


def test_un_melange_de_dates_et_d_absences_reste_correct(tmp_path, monkeypatch):
    """Le cas courant : la plupart des lignes ont une échéance, certaines non.

    Sert de garde-fou dans l'autre sens — la correction ne doit pas casser le cas
    normal, déjà couvert ailleurs mais jamais en passant par le VRAI export.
    """
    from datetime import date

    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "test.db")

    df = _df([
        {"deadline": date(2020, 1, 1)},   # passée
        {"deadline": date(2999, 1, 1)},   # future
        {"deadline": None},               # absente
    ])
    assert duckdb_export.export_dataframe(df)

    con = duckdb.connect(str(tmp_path / "test.db"), read_only=True)
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE deadline <= CURRENT_DATE"
    ).fetchall() == [(1,)]
    assert con.execute(
        "SELECT COUNT(*) FROM opportunities WHERE deadline IS NULL"
    ).fetchall() == [(1,)]


def test_le_dataframe_source_n_est_pas_modifie_par_l_export(tmp_path, monkeypatch):
    """`df` reste celui que `db_layer.py` interroge en parallèle du chat.

    Le forcer en place introduirait un effet de bord sur la source de vérité de
    l'application pour un besoin qui n'appartient qu'à cette projection DuckDB.
    """
    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "test.db")

    df = _df([{"deadline": None}])
    dtype_avant = df["deadline"].dtype
    duckdb_export.export_dataframe(df)

    assert df["deadline"].dtype == dtype_avant
