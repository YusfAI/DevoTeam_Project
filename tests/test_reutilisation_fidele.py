"""Une section ne peut répondre à une question que si elle en donne LE MÊME chiffre.

Rediriger vers une page toute faite au lieu d'en composer une neuve n'a de valeur
que si la page dit la même chose que la phrase qu'on vient de lire. Sinon c'est pire
que de composer : l'utilisateur lit « 103 900 001 DT » dans le chat et voit 75 400 000
à l'écran, sans rien pour lui dire laquelle des deux réponses est la sienne.

La première table de routage était écrite de mémoire — métrique et axe semblaient
coïncider — et cinq de ses huit entrées désignaient une page répondant à une autre
question, dont « budget par pays » qui menait à une section sans aucun widget par
pays. Ce test rejoue les deux moteurs et refuse toute entrée non tenue.
"""
import re

import duckdb
import pytest
import yaml

from backend import db_layer
from backend.overview_match import _REPONSES
from tests.test_accueil_dashboard import (
    COLONNES, DASHBOARDS, _opportunite, _sans_jinja,
)


def _df(lignes):
    import pandas as pd
    return pd.DataFrame([_opportunite(**l) for l in lignes])


def _valeur(v):
    import pandas as pd
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _duckdb_avec(df):
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    for ligne in df.to_dict("records"):
        con.execute("INSERT INTO opportunities VALUES (%s)"
                    % ", ".join("?" for _ in COLONNES),
                    [_valeur(ligne[nom]) for nom, _ in COLONNES])
    return con


def _widgets_de(page):
    for fichier in DASHBOARDS.glob("*.yml"):
        doc = yaml.safe_load(fichier.read_text(encoding="utf-8"))
        if doc.get("name") == page:
            return [w for r in (doc.get("rows") or []) for w in r["widgets"]]
    raise AssertionError("section introuvable sur le disque : %r" % page)


# Un jeu volontairement contrasté : plusieurs practices, plusieurs pays, et des
# statuts des deux côtés de la frontière « actif / mort ». Un échantillon uniforme
# laisserait passer une divergence de périmètre en donnant le même total partout.
LIGNES = [
    {"id": 1, "country": "Tunisie", "practice": "Risk Advisory",
     "status": "Offre remise", "budget": 100000.0, "financial_offer": 90000.0,
     "win_probability": 0.5, "weighted_amount": 50000.0},
    {"id": 2, "country": "France", "practice": "Data Management",
     "status": "Offre gagnée", "budget": 200000.0, "financial_offer": 180000.0,
     "win_probability": 1.0, "weighted_amount": 200000.0},
    {"id": 3, "country": "Bénin", "practice": "Digital Transformation",
     "status": "Lead", "budget": 50000.0, "financial_offer": 40000.0,
     "win_probability": 0.3, "weighted_amount": 15000.0},
    # Morte : elle doit sortir des DEUX côtés, ou l'écart se verra.
    {"id": 4, "country": "Tunisie", "practice": "Risk Advisory",
     "status": "Offre perdue", "budget": 400000.0, "financial_offer": 380000.0,
     "win_probability": 0.0, "weighted_amount": 0.0},
    {"id": 5, "country": "Maroc", "practice": "Data Management",
     "status": "NO GO", "budget": 300000.0, "financial_offer": 290000.0,
     "win_probability": 0.0, "weighted_amount": 0.0},
]


@pytest.mark.parametrize("cle,page", sorted(_REPONSES.items()))
def test_la_section_donne_exactement_le_chiffre_annonce(cle, page, monkeypatch):
    metrique, axe = cle
    df = _df(LIGNES)
    # Les deux moteurs doivent voir LES MÊMES lignes, sinon la comparaison ne prouve
    # rien : le chat interrogerait la production pendant que le widget lit le jeu
    # d'essai, et l'écart mesuré serait celui des données, pas celui des requêtes.
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)

    intent = {"metric": metrique, "dimension": axe, "filters": {},
              "range_filters": {}, "aggregation": "sum", "use_raw_table": False,
              "limit": 0, "exclude_statuses": []}
    attendu = db_layer.build_and_execute_query(intent)
    somme = sum((r.get("value") if r.get("value") is not None else r.get(metrique)) or 0
                for r in attendu)

    con = _duckdb_avec(df)
    concordants = []
    for w in _widgets_de(page):
        if not w.get("sql"):
            continue
        try:
            lignes = con.execute(_sans_jinja(w["sql"])).fetchall()
        except duckdb.Error:
            # Un widget peut viser d'autres colonnes ; seul un widget QUI RÉPOND
            # nous intéresse, pas la santé de tous les autres (déjà testée ailleurs).
            continue
        total = sum(l[-1] or 0 for l in lignes if isinstance(l[-1], (int, float)))
        if abs(total - somme) < 0.5 and len(lignes) == len(attendu):
            concordants.append(w["name"])

    assert concordants, (
        "« %s » ne contient aucun widget qui rende %s = %s sur %d ligne(s). "
        "Cette entrée renverrait l'utilisateur vers une page qui contredit la "
        "réponse du chat : retirez-la de _REPONSES, ou ajoutez le widget."
        % (page, metrique, somme, len(attendu)))


def test_une_entree_fausse_serait_bien_detectee(monkeypatch):
    """Le test ci-dessus ne vaut que s'il sait dire non.

    Sans cette vérification, une comparaison trop permissive — un widget accepté
    parce qu'il rend « un nombre » — passerait pour une preuve tout en n'en étant
    pas une, et la table pourrait se repeupler d'entrées fausses.
    """
    df = _df(LIGNES)
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)
    con = _duckdb_avec(df)

    # « budget par pays » sur la santé du portefeuille : l'erreur d'origine.
    intent = {"metric": "budget", "dimension": "country", "filters": {},
              "range_filters": {}, "aggregation": "sum", "use_raw_table": False,
              "limit": 0, "exclude_statuses": []}
    attendu = db_layer.build_and_execute_query(intent)
    somme = sum((r.get("value") if r.get("value") is not None else r.get("budget")) or 0
                for r in attendu)

    concordants = []
    for w in _widgets_de("Santé du portefeuille"):
        if not w.get("sql"):
            continue
        try:
            lignes = con.execute(_sans_jinja(w["sql"])).fetchall()
        except duckdb.Error:
            continue
        total = sum(l[-1] or 0 for l in lignes if isinstance(l[-1], (int, float)))
        if abs(total - somme) < 0.5 and len(lignes) == len(attendu):
            concordants.append(w["name"])

    assert not concordants, concordants
