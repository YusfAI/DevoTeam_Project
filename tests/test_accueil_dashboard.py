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
# Affaires chaudes : le seuil est un MINIMUM, pas une égalité
# ---------------------------------------------------------------------------

def test_a_deal_above_the_threshold_is_included(base):
    # Le cœur du sujet : 100 % doit entrer. Sur les vraies données aucune affaire en
    # jeu ne dépasse 80 %, donc seule une ligne fabriquée peut le prouver.
    _remplir(base, [
        _opportunite(buyer="Certaine", win_probability=1.0),
        _opportunite(buyer="Presque sûre", win_probability=0.9,
                      status="En attente du plan de charge"),
        _opportunite(buyer="Au seuil", win_probability=0.8),
    ])
    lignes = _executer(base, "Détail des affaires chaudes")
    assert {l[1] for l in lignes} == {"Certaine", "Presque sûre", "Au seuil"}


def test_a_deal_below_the_threshold_is_excluded(base):
    _remplir(base, [
        _opportunite(buyer="Au seuil", win_probability=0.8),
        _opportunite(buyer="Juste en dessous", win_probability=0.79),
    ])
    lignes = _executer(base, "Détail des affaires chaudes")
    assert [l[1] for l in lignes] == ["Au seuil"]


def test_the_status_plays_no_part(base):
    # Décision métier explicite : seule la probabilité décide. Une affaire déjà
    # gagnée est à 100 %, donc chaude elle aussi — c'est ce qui fait passer le
    # compte de 14 à 105 sur les vraies données.
    _remplir(base, [
        _opportunite(buyer="Gagnée", status="Offre gagnée", win_probability=1.0),
        _opportunite(buyer="Signée", status="Offre signée", win_probability=1.0),
        _opportunite(buyer="Remise", status="Offre remise", win_probability=0.8),
        _opportunite(buyer="Amont", status="Lead", win_probability=1.0),
    ])
    lignes = _executer(base, "Détail des affaires chaudes")
    assert {l[1] for l in lignes} == {"Gagnée", "Signée", "Remise", "Amont"}


def test_an_opportunity_without_a_probability_stays_out(base):
    # Les 63 offres perdues ont une pondération vide dans le Sheet : elles sortent
    # d'elles-mêmes, une comparaison avec une valeur absente étant toujours fausse.
    # Aucun filtre de statut n'est donc nécessaire pour les écarter.
    _remplir(base, [
        _opportunite(buyer="Sans pondération", status="Offre perdue", win_probability=None,
                      weighted_amount=None),
        _opportunite(buyer="Avec pondération", win_probability=0.8),
    ])
    lignes = _executer(base, "Détail des affaires chaudes")
    assert [l[1] for l in lignes] == ["Avec pondération"]


def test_the_hot_deal_kpis_agree_with_the_table(base):
    _remplir(base, [
        _opportunite(win_probability=1.0, budget=200000.0, weighted_amount=200000.0),
        _opportunite(win_probability=0.8, budget=100000.0, weighted_amount=72000.0),
        _opportunite(win_probability=0.4, budget=999999.0, weighted_amount=1.0),
    ])
    assert _executer(base, "Affaires chaudes")[0][0] == 2
    assert _executer(base, "Budget à forte confiance")[0][0] == 300000.0
    assert _executer(base, "Montant pondéré associé")[0][0] == 272000.0
    assert len(_executer(base, "Détail des affaires chaudes")) == 2


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


def test_the_table_holds_every_hot_deal(base):
    # Aucune ligne n'est retirée : la taille du widget est bornée par la hauteur de sa
    # LIGNE de grille, pas en amputant la requête. Un LIMIT rendrait les affaires
    # suivantes définitivement inatteignables, molette ou pas.
    _remplir(base, [_opportunite(buyer="Client %02d" % i, win_probability=0.8,
                                  weighted_amount=float(1000 - i))
                     for i in range(25)])

    assert _executer(base, "Affaires chaudes")[0][0] == 25
    lignes = _executer(base, "Détail des affaires chaudes")
    assert len(lignes) == 25
    # Et triées par espérance de gain décroissante : la plus forte se lit sans défiler.
    assert [l[1] for l in lignes] == ["Client %02d" % i for i in range(25)]


def test_the_hot_deal_row_is_height_bounded():
    """C'est ce qui rend le défilement possible.

    Le widget est en `h-full` dans sa cellule de grille ; sans hauteur sur la ligne,
    la cellule s'étire avec le contenu et le tableau occupe toute la page. Avec elle,
    le conteneur du tableau — qui porte `overflow-x-auto`, ce qui fait calculer `auto`
    pour l'axe vertical — défile à la molette. `height` n'est accepté QUE sur la
    ligne : le schéma DAC le refuse sur un widget.
    """
    doc = yaml.safe_load(ACCUEIL.read_text(encoding="utf-8"))
    lignes = [r for r in doc["rows"]
               if any(w["name"] == "Détail des affaires chaudes" for w in r["widgets"])]

    assert len(lignes) == 1
    assert isinstance(lignes[0].get("height"), int)


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
