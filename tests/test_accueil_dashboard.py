"""Exécute le SQL de la vue d'ensemble sur des données synthétiques.

`dac check` prouve que chaque requête s'exécute, pas qu'elle sélectionne les bonnes
lignes : les vraies données ne contiennent aucune prévision entre 80 % et 100 %, donc
remplacer « >= 80 % » par « = 80 % » ne changerait aucun chiffre affiché et passerait
inaperçu. Ces tests fabriquent les lignes que les vraies données n'ont pas.
"""
import re
from pathlib import Path

import duckdb
import pytest
import yaml

ACCUEIL = Path(__file__).resolve().parent.parent / "dac" / "dashboards" / "accueil.yml"

COLONNES = [
    ("id", "INTEGER"), ("country", "VARCHAR"), ("buyer", "VARCHAR"),
    ("description", "VARCHAR"), ("practice", "VARCHAR"), ("status", "VARCHAR"),
    ("budget", "DOUBLE"), ("financial_offer", "DOUBLE"), ("win_probability", "DOUBLE"),
    ("weighted_amount", "DOUBLE"), ("deadline", "DATE"), ("deadline_month", "VARCHAR"),
    ("deadline_year", "INTEGER"), ("days_remaining", "INTEGER"),
]


def _widget(nom: str) -> dict:
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    for row in doc["rows"]:
        for widget in row["widgets"]:
            if widget["name"] == nom:
                return widget
    raise AssertionError("widget introuvable dans accueil.yml : %r" % nom)


def _sans_jinja(sql: str) -> str:
    """Rend la requête comme DAC le ferait avec les filtres sur « tout » : chaque bloc
    conditionnel est retiré EN ENTIER, corps compris. Ne retirer que les balises
    laisserait la condition en place et ne sélectionnerait plus rien."""
    return re.sub(r"\{%\s*if.*?\{%\s*endif\s*%\}", "", sql, flags=re.S)


def _opportunite(**champs):
    base = {
        "id": 1, "country": "France", "buyer": "Client", "description": "Mission",
        "practice": "Risk Advisory", "status": "Offre remise", "budget": 100000.0,
        "financial_offer": 90000.0, "win_probability": 0.8, "weighted_amount": 72000.0,
        "deadline": "2026-01-15", "deadline_month": "2026-01", "deadline_year": 2026,
        "days_remaining": 30,
    }
    base.update(champs)
    return base


@pytest.fixture
def base():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    return con


def _remplir(con, lignes):
    for i, ligne in enumerate(lignes, start=1):
        ligne.setdefault("id", i)
        con.execute(
            "INSERT INTO opportunities VALUES (%s)" % ", ".join("?" for _ in COLONNES),
            [ligne[nom] for nom, _ in COLONNES],
        )


def _executer(con, nom_widget):
    return con.execute(_sans_jinja(_widget(nom_widget)["sql"])).fetchall()


# ---------------------------------------------------------------------------
# Affaires chaudes : les KPI restés dans le dashboard
#
# Le tableau de détail, lui, a quitté le YAML : il est rendu par l'application faute
# de défilement vertical dans le tableau de DAC. Sa définition et son accord avec ces
# KPI sont vérifiés dans tests/test_hot_deals.py.
# ---------------------------------------------------------------------------

def test_the_hot_deal_kpis_count_every_deal_above_the_threshold(base):
    _remplir(base, [
        _opportunite(win_probability=1.0, budget=200000.0, weighted_amount=200000.0),
        _opportunite(win_probability=0.8, budget=100000.0, weighted_amount=72000.0),
        _opportunite(win_probability=0.4, budget=999999.0, weighted_amount=1.0),
    ])
    assert _executer(base, "Affaires chaudes")[0][0] == 2
    assert _executer(base, "Budget à forte confiance (DT)")[0][0] == 300000.0
    assert _executer(base, "Montant pondéré associé (DT)")[0][0] == 272000.0


def test_a_won_deal_counts_as_hot_for_the_kpis_too(base):
    # Le statut ne joue aucun rôle, côté SQL comme côté Python.
    _remplir(base, [
        _opportunite(status="Offre gagnée", win_probability=1.0),
        _opportunite(status="Lead", win_probability=1.0),
        _opportunite(status="Offre perdue", win_probability=None, weighted_amount=None),
    ])
    assert _executer(base, "Affaires chaudes")[0][0] == 2


# ---------------------------------------------------------------------------
# Offres remises : les trois issues doivent faire le total
# ---------------------------------------------------------------------------

def test_the_outcomes_add_up_to_the_submitted_total(base):
    # Un statut oublié dans l'une des trois listes donnerait un dashboard dont les
    # parties ne font pas le tout, sans qu'aucune requête n'échoue pour autant.
    _remplir(base, [
        _opportunite(status="Offre gagnée"),
        _opportunite(status="Offre signée"),
        _opportunite(status="Offre perdue"),
        _opportunite(status="Offre remise"),
        _opportunite(status="En attente du plan de charge"),
        _opportunite(status="Lead"),          # jamais remise
        _opportunite(status="NO GO"),         # jamais remise
    ])
    total = _executer(base, "Offres remises")[0][0]
    gagnees = _executer(base, "Gagnées")[0][0]
    perdues = _executer(base, "Perdues")[0][0]
    attente = _executer(base, "En attente")[0][0]

    assert total == 5
    assert gagnees + perdues + attente == total


def test_an_offer_whose_deadline_has_not_come_is_not_submitted_yet(base):
    # « À date » : l'échéance tient lieu de date de remise, la borne haute est le jour
    # même. Une échéance à venir signifie que l'offre n'est pas encore partie.
    _remplir(base, [
        _opportunite(status="Offre remise", deadline="2026-01-15"),
        _opportunite(status="Offre remise", deadline="2099-12-31"),
    ])
    assert _executer(base, "Offres remises")[0][0] == 1


def test_the_win_rate_ignores_the_offers_still_pending(base):
    # Une offre en attente n'est ni un succès ni un échec : la compter au
    # dénominateur écraserait le taux sans rien dire de vrai.
    _remplir(base, [
        _opportunite(status="Offre gagnée"),
        _opportunite(status="Offre gagnée"),
        _opportunite(status="Offre gagnée"),
        _opportunite(status="Offre perdue"),
        _opportunite(status="Offre remise"),
        _opportunite(status="Offre remise"),
    ])
    assert _executer(base, "Taux de réussite")[0][0] == pytest.approx(0.75)


def test_every_widget_explains_itself_briefly():
    # Une phrase sous le titre, assez courte pour être lue d'un coup d'œil. Le
    # raisonnement long vit en commentaire YAML, où il sert la revue sans encombrer
    # l'écran.
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    widgets = [w for row in doc["rows"] for w in row["widgets"]]

    sans_description = [w["name"] for w in widgets if not (w.get("description") or "").strip()]
    bavardes = [w["name"] for w in widgets if len((w.get("description") or "").strip()) > 100]

    assert not sans_description, sans_description
    assert not bavardes, bavardes


# ---------------------------------------------------------------------------
# Le filtre de période
# ---------------------------------------------------------------------------

def test_the_period_is_two_named_date_fields():
    """Deux champs plutôt qu'un sélecteur de plage : les bornes sont nommées.

    Le libellé affiché EST le nom du filtre, tirets bas convertis en espaces — le
    schéma n'a pas de champ `label`. Le nom porte donc ce que l'utilisateur lit, et
    reste sans accent puisqu'il sert aussi d'identifiant dans les gabarits Jinja.
    """
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    dates = [f for f in doc["filters"] if f["type"] == "date"]

    assert [f["name"] for f in dates] == ["Date_de_debut", "Date_de_fin"]
    assert all(f["name"].isascii() for f in dates)
    assert dates[0]["default"] < dates[1]["default"]


def test_each_bound_applies_only_if_it_exists():
    """Vider un champ doit lever CETTE borne et garder l'autre.

    Un BETWEEN sur les deux ne le permettrait pas : effacer une date ne rendrait
    plus une seule ligne au lieu d'ouvrir ce côté de la période.
    """
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    sql = next(w for row in doc["rows"] for w in row["widgets"]
                if w["name"] == "Budget actif (DT)")["sql"]

    assert "{% if filters.Date_de_debut %}" in sql
    assert "{% if filters.Date_de_fin %}" in sql
    assert "BETWEEN DATE" not in sql


def test_the_urgent_table_ignores_the_period():
    # Sa fenêtre est « les 7 prochains jours » : une plage se terminant aujourd'hui
    # la viderait entièrement, ce qui est le contraire de son propos. Le filtre de
    # practice, lui, doit continuer de s'appliquer.
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    sql = next(w for row in doc["rows"] for w in row["widgets"]
                if w["name"].startswith("Opportunités urgentes"))["sql"]

    assert "filters.Date_de_debut" not in sql
    assert "filters.Date_de_fin" not in sql
    assert "filters.practice" in sql


def test_every_other_widget_follows_the_two_dates():
    # Un widget oublié afficherait un chiffre d'un autre périmètre que ses voisins,
    # sans qu'aucune requête n'échoue.
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    oublis = [w["name"] for row in doc["rows"] for w in row["widgets"]
               if ("filters.Date_de_debut" not in w["sql"]
                    or "filters.Date_de_fin" not in w["sql"])
               and not w["name"].startswith("Opportunités urgentes")]
    assert not oublis, oublis


# ---------------------------------------------------------------------------
# L'unité des montants
# ---------------------------------------------------------------------------

def test_amounts_carry_their_unit_and_never_a_currency_format():
    """Les montants sont en dinars, et DAC ne sait pas l'écrire à côté du nombre.

    Son schéma refuse `suffix`, `unit` et `prefix` sur une valeur, et son format
    `currency` applique le préfixe `$` de son formateur d3 — soit des dollars
    affichés là où il s'agit de dinars. L'unité vit donc sur les libellés, et le
    format `currency` ne doit plus apparaître nulle part.
    """
    from backend.labels import DEVISE

    contenu = ACCUEIL.read_text(encoding="utf-8")
    doc = yaml.safe_load(contenu)
    widgets = [w for row in doc["rows"] for w in row["widgets"]]

    assert "number: currency" not in contenu

    # Tout libellé qui parle d'argent porte l'unité — sauf s'il n'affiche pas un
    # montant : « Écart offre / budget » est un pourcentage, mettre « DT » à côté
    # serait faux. C'est donc le FORMAT qui décide, pas le seul intitulé.
    argent = ("budget", "montant", "offre financière")

    def montre_un_montant(widget):
        format_ = str((widget.get("value") or {}).get("format", ""))
        return not format_.endswith("%")

    sans_unite = [
        w["name"] for w in widgets
        if montre_un_montant(w)
        and any(mot in w["name"].lower() for mot in argent)
        and DEVISE not in w["name"]
    ]
    assert not sans_unite, sans_unite

    colonnes_sans_unite = [
        c["label"] for w in widgets for c in w.get("columns", [])
        if any(mot in c["label"].lower() for mot in argent) and DEVISE not in c["label"]
    ]
    assert not colonnes_sans_unite, colonnes_sans_unite
