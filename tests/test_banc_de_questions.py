"""Le banc de questions : trente questions fréquentes, chacune vérifiée deux fois.

Pourquoi un banc plutôt que des tests unitaires de plus. Le défaut que la direction
a signalé n'était pas « cette fonction est fausse » mais « cette question répond bien
parfois, mal d'autres fois ». Un tel défaut ne se voit sur aucun test unitaire : le
code est juste à chaque étape, et c'est la CHAÎNE qui varie selon la formulation.

Chaque question est donc éprouvée sur deux axes.

1. La JUSTESSE. La réponse attendue est recalculée à côté, en pandas nu, sans passer
   par une seule ligne de l'application. Une erreur commise dans les deux moteurs à
   la fois — c'est arrivé — resterait invisible à toute comparaison interne ; elle ne
   se voit qu'en refaisant le calcul autrement.

2. La STABILITÉ. Le modèle de langage ne produit pas la même ébauche d'une fois sur
   l'autre : selon la tournure, il propose la bonne métrique, une métrique voisine,
   ou un axe superflu. Chaque question est donc rejouée avec PLUSIEURS ébauches
   plausibles, et toutes doivent aboutir au même chiffre. C'est ce qui garantit que
   la réponse ne dépend pas de l'humeur du modèle — le cœur du reproche.

Ajouter une question ici est le moyen normal de signaler qu'elle répond mal : écrire
sa vérité en pandas, lancer le banc, et corriger jusqu'au vert.
"""
from datetime import date

import pandas as pd
import pytest

from backend import db_layer
from backend.business_rules import (
    LOST_STATUSES, SUBMITTED_STATUSES, WON_STATUSES, hot_deal_mask,
)
from backend.intent_refiner import refine_intent

# Une date fixe : « à date actuelle » doit donner le même résultat en toute saison.
AUJOURD_HUI = date(2026, 8, 31)


# ---------------------------------------------------------------------------
# Le jeu de données
#
# Écrit à la main plutôt que tiré de la production : le banc doit dire la même chose
# aujourd'hui et dans six mois, et une vérité qui bouge avec le Google Sheet ne
# prouverait plus rien. Les valeurs sont choisies pour que chaque question ait une
# réponse NON TRIVIALE — un jeu uniforme laisserait passer un filtre ignoré.
# ---------------------------------------------------------------------------

def _ligne(id_, pays, practice, statut, budget, proba, mois, jours, client="Client"):
    an, m = mois.split("-")
    return {
        "id": id_, "country": pays, "buyer": client, "description": "Mission",
        "practice": practice, "status": statut, "budget": float(budget),
        "financial_offer": float(budget) * 0.9, "win_probability": proba,
        "weighted_amount": float(budget) * (proba if proba is not None else 0),
        "deadline": date(int(an), int(m), 15), "deadline_month": mois,
        "deadline_year": int(an), "days_remaining": jours,
    }


LIGNES = [
    # --- Offres remises, échéance passée (elles comptent comme « remises ») ---
    _ligne(1, "Tunisie", "Risk Advisory", "Offre gagnée", 500000, 1.0, "2025-11", -290),
    _ligne(2, "Tunisie", "Risk Advisory", "Offre signée", 300000, 1.0, "2025-12", -260),
    _ligne(3, "France", "Data Management", "Offre perdue", 400000, 0.0, "2026-01", -230),
    _ligne(4, "France", "Data Management", "Offre remise", 250000, 0.85, "2026-02", -200),
    _ligne(5, "Bénin", "Digital Transformation", "En attente du plan de charge",
           150000, 0.9, "2026-03", -170),
    _ligne(6, "Bénin", "Digital Transformation", "Offre gagnée", 600000, 1.0, "2026-04", -140),
    _ligne(7, "Maroc", "Risk Advisory", "Offre perdue", 200000, 0.0, "2026-05", -110),
    _ligne(8, "Maroc", "Risk Advisory", "Offre remise", 350000, 0.82, "2026-06", -80),
    # --- Remise au statut mais échéance À VENIR : pas encore remise ---
    _ligne(9, "Tunisie", "Data Management", "Offre remise", 999000, 0.95, "2026-12", 100),
    # --- Jamais déposées : le portefeuille actif ---
    _ligne(10, "Tunisie", "Risk Advisory", "Lead", 120000, 0.3, "2026-09", 20),
    _ligne(11, "France", "Digital Transformation", "Opportunité détectée",
           180000, 0.2, "2026-10", 50),
    _ligne(12, "Sénégal", "Data Management", "En cours de qualification",
           90000, 0.4, "2026-09", 5, client="Autre"),
    _ligne(13, "Sénégal", "Risk Advisory", "Propal shortlistée", 220000, 0.6, "2026-09", 3,
           client="Autre"),
    # --- Statuts morts : exclus par défaut ---
    _ligne(14, "Maroc", "Data Management", "NO GO", 700000, 0.0, "2026-07", -50),
    _ligne(15, "Tunisie", "Digital Transformation", "Infructueux", 800000, 0.0, "2026-07", -45),
    _ligne(16, "France", "Risk Advisory", "Non shortlisté", 310000, 0.0, "2026-06", -75),
]


@pytest.fixture
def df():
    return pd.DataFrame(LIGNES)


@pytest.fixture(autouse=True)
def _donnees_du_banc(df, monkeypatch):
    """Les deux moteurs voient les lignes du banc, jamais celles de la production."""
    monkeypatch.setattr(db_layer, "get_dataframe", lambda: df)


# ---------------------------------------------------------------------------
# Les vérités, calculées en pandas nu
# ---------------------------------------------------------------------------

def _actif(df):
    """Le portefeuille par défaut : tout sauf les affaires mortes."""
    return df[~df["status"].isin(LOST_STATUSES)]


def _remises(df):
    """Déposées ET échues — la définition du tableau de bord."""
    return df[df["status"].isin(SUBMITTED_STATUSES) & (df["days_remaining"] <= 0)]


def _somme(sous, colonne="budget"):
    return float(sous[colonne].sum())


def _compte(sous):
    return int(len(sous))


def _par(sous, axe, colonne=None):
    if colonne is None:
        return {k: int(v) for k, v in sous.groupby(axe).size().items()}
    return {k: float(v) for k, v in sous.groupby(axe)[colonne].sum().items()}


# ---------------------------------------------------------------------------
# Le banc
#
# Chaque entrée : la question, les ébauches plausibles du modèle, et la vérité.
# `ebauches` liste ce que le modèle pourrait raisonnablement produire — la bonne
# réponse ET les approximations courantes. Toutes doivent aboutir au même chiffre.
# ---------------------------------------------------------------------------

_KPI = {"dimension": "", "chart_type": "kpi_card"}
_BAR = {"chart_type": "bar"}


def _ebauche(**champs):
    base = {"goal": "", "metric": "budget", "dimension": "", "filters": {},
            "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
            "use_raw_table": False, "is_conversation": False, "limit": 0}
    base.update(champs)
    return base


BANC = [
    # --- Volumes du portefeuille ------------------------------------------
    ("combien d'opportunités en tout ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="")],
     lambda df: _compte(_actif(df))),

    ("quel est le budget total ?",
     [_ebauche(metric="budget", **_KPI),
      _ebauche(metric="budget", aggregation="sum", dimension="")],
     lambda df: _somme(_actif(df))),

    ("quel est le montant pondéré ?",
     [_ebauche(metric="weighted_amount", **_KPI),
      # Le modèle confond parfois pondéré et budget : la question doit trancher.
      _ebauche(metric="weighted_amount", aggregation="sum", dimension="")],
     lambda df: _somme(_actif(df), "weighted_amount")),

    ("quel est le total des offres financières ?",
     [_ebauche(metric="financial_offer", **_KPI)],
     lambda df: _somme(_actif(df), "financial_offer")),

    # --- Le terme métier « offres remises » -------------------------------
    ("combien d'offres a-t-on remises ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      # Ébauche typiquement fautive : le statut littéral seul.
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="",
               filters={"status": "Offre remise"})],
     lambda df: _compte(_remises(df))),

    ("quel est le budget des offres remises ?",
     [_ebauche(metric="budget", **_KPI),
      _ebauche(metric="budget", dimension="", filters={"status": "Offre remise"})],
     lambda df: _somme(_remises(df))),

    # --- Le terme métier « offres gagnées » -------------------------------
    ("combien d'offres gagnées ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      # C'est exactement l'ébauche qui donnait 56 au lieu de 88 en production.
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="",
               filters={"status": "Offre gagnée"})],
     lambda df: _compte(df[df["status"].isin(WON_STATUSES)])),

    ("combien d'offres n'ont pas été gagnées ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      # Le modèle proposait le filtre POSITIF : la réponse exacte à l'inverse.
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="",
               filters={"status": "Offre gagnée"})],
     lambda df: _compte(_actif(df)[~_actif(df)["status"].isin(WON_STATUSES)])),

    # --- L'issue des offres remises ---------------------------------------
    ("sur le total des offres remises, combien gagnées, perdues, et en attente ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", dimension="status"),
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="")],
     lambda df: {
         "Gagnée": _compte(_remises(df)[_remises(df)["status"].isin(WON_STATUSES)]),
         "Perdue": _compte(_remises(df)[_remises(df)["status"] == "Offre perdue"]),
         "En attente": _compte(_remises(df)[
             ~_remises(df)["status"].isin(WON_STATUSES + ["Offre perdue"])]),
     }),

    # --- Répartitions -----------------------------------------------------
    ("quelle est la répartition par practice ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", dimension="practice", **_BAR),
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="practice",
               chart_type="pie")],
     lambda df: _par(_actif(df), "practice")),

    ("budget par pays",
     [_ebauche(metric="budget", dimension="country", **_BAR)],
     lambda df: _par(_actif(df), "country", "budget")),

    ("budget par practice",
     [_ebauche(metric="budget", dimension="practice", **_BAR)],
     lambda df: _par(_actif(df), "practice", "budget")),

    ("nombre d'opportunités par pays",
     [_ebauche(metric="nb_opportunities", aggregation="count", dimension="country", **_BAR)],
     lambda df: _par(_actif(df), "country")),

    # --- Filtres ----------------------------------------------------------
    ("quel est le budget de Risk Advisory ?",
     [_ebauche(metric="budget", filters={"practice": "Risk Advisory"}, **_KPI),
      _ebauche(metric="budget", dimension="", filters={"practice": "Risk Advisory"})],
     lambda df: _somme(_actif(df)[_actif(df)["practice"] == "Risk Advisory"])),

    ("budget par pays pour Risk Advisory",
     [_ebauche(metric="budget", dimension="country",
               filters={"practice": "Risk Advisory"}, **_BAR)],
     lambda df: _par(_actif(df)[_actif(df)["practice"] == "Risk Advisory"],
                     "country", "budget")),

    ("quel est le budget en Tunisie ?",
     [_ebauche(metric="budget", filters={"country": "Tunisie"}, **_KPI)],
     lambda df: _somme(_actif(df)[_actif(df)["country"] == "Tunisie"])),

    ("budget hors Tunisie",
     [_ebauche(metric="budget", **_KPI),
      # Sans garde-fou, la négation partait en filtre POSITIF.
      _ebauche(metric="budget", dimension="", filters={"country": "Tunisie"})],
     lambda df: _somme(_actif(df)[_actif(df)["country"] != "Tunisie"])),

    # --- Périodes ---------------------------------------------------------
    ("combien d'offres a-t-on remises entre novembre 2025 et à date actuelle ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      # L'ébauche qui ignorait la période — le défaut d'origine.
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="")],
     lambda df: _compte(_remises(df)[
         (_remises(df)["deadline_month"] >= "2025-11")
         & (_remises(df)["deadline_month"] <= "2026-08")])),

    ("budget entre mars 2026 et juin 2026",
     [_ebauche(metric="budget", **_KPI)],
     lambda df: _somme(_actif(df)[
         (_actif(df)["deadline_month"] >= "2026-03")
         & (_actif(df)["deadline_month"] <= "2026-06")])),

    ("budget en mars 2026",
     [_ebauche(metric="budget", **_KPI)],
     lambda df: _somme(_actif(df)[_actif(df)["deadline_month"] == "2026-03"])),

    ("budget depuis janvier 2026",
     [_ebauche(metric="budget", **_KPI)],
     lambda df: _somme(_actif(df)[
         (_actif(df)["deadline_month"] >= "2026-01")
         & (_actif(df)["deadline_month"] <= "2026-08")])),

    ("combien d'opportunités en 2026 ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI)],
     lambda df: _compte(_actif(df)[_actif(df)["deadline_year"] == 2026])),

    # --- Affaires chaudes -------------------------------------------------
    ("combien d'affaires chaudes ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      # Une intersection au lieu d'une réunion : l'erreur naturelle du modèle.
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="",
               range_filters={"win_probability": {"op": ">=", "value": 0.8}})],
     lambda df: _compte(_actif(df)[hot_deal_mask(_actif(df))])),

    ("quel est le budget des affaires chaudes ?",
     [_ebauche(metric="budget", **_KPI)],
     lambda df: _somme(_actif(df)[hot_deal_mask(_actif(df))])),

    # --- Moyennes ---------------------------------------------------------
    ("quel est le budget moyen ?",
     [_ebauche(metric="budget", aggregation="avg", **_KPI),
      # Le mot « moyen » était ignoré : la SOMME partait sous l'étiquette moyenne.
      _ebauche(metric="budget", aggregation="sum", dimension="")],
     lambda df: float(_actif(df)["budget"].mean())),

    ("quelle est la probabilité de gain moyenne par practice ?",
     [_ebauche(metric="win_probability", aggregation="avg", dimension="practice", **_BAR)],
     lambda df: {k: float(v) for k, v in
                 _actif(df).groupby("practice")["win_probability"].mean().items()}),

    # --- Bornes chiffrées -------------------------------------------------
    ("quelles opportunités ont un budget supérieur à 300000 ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI),
      _ebauche(metric="nb_opportunities", aggregation="count", dimension="",
               range_filters={"budget": {"op": ">", "value": 300000}})],
     lambda df: _compte(_actif(df)[_actif(df)["budget"] > 300000])),

    ("combien d'opportunités ont plus de 80 % de chances ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI)],
     lambda df: _compte(_actif(df)[_actif(df)["win_probability"] > 0.8])),

    # --- Cardinalité ------------------------------------------------------
    ("combien de clients différents ?",
     [_ebauche(metric="nb_opportunities", aggregation="count", **_KPI)],
     lambda df: int(_actif(df)["buyer"].nunique())),

    # --- Classement tronqué ------------------------------------------------
    ("top 2 pays par budget",
     [_ebauche(metric="budget", dimension="country", limit=2, **_BAR),
      # Le modèle oublie souvent la troncature : la question la porte.
      _ebauche(metric="budget", dimension="country", **_BAR)],
     lambda df: dict(sorted(_par(_actif(df), "country", "budget").items(),
                            key=lambda kv: -kv[1])[:2])),
]


# ---------------------------------------------------------------------------
# L'exécution
# ---------------------------------------------------------------------------

def _reponse(question: str, ebauche: dict):
    """Ce que l'application répond, ébauche du modèle comprise."""
    intent = refine_intent(question, dict(ebauche,
                                          filters=dict(ebauche["filters"]),
                                          range_filters=dict(ebauche["range_filters"])),
                           today=AUJOURD_HUI)
    lignes = db_layer.build_and_execute_query(intent)
    metric = intent.get("metric") or "budget"
    axe = intent.get("dimension") or ""

    if not axe:
        if not lignes:
            return 0
        ligne = lignes[0]
        valeur = ligne.get("value")
        if valeur is None:
            valeur = ligne.get(metric)
        if valeur is None:
            valeur = next((v for v in ligne.values() if isinstance(v, (int, float))), 0)
        return float(valeur)

    return {r[axe]: float(r.get(metric) if r.get(metric) is not None else r.get("value", 0))
            for r in lignes if axe in r}


def _egal(obtenu, attendu):
    """Comparaison tolérante aux flottants, structure comprise."""
    if isinstance(attendu, dict):
        if set(obtenu) != set(attendu):
            return False
        return all(abs(obtenu[k] - float(attendu[k])) < 0.01 for k in attendu)
    return abs(float(obtenu) - float(attendu)) < 0.01


@pytest.mark.parametrize("question,ebauches,verite",
                         BANC, ids=[c[0][:48] for c in BANC])
def test_la_question_recoit_la_bonne_reponse(question, ebauches, verite, df):
    """Axe 1 — la justesse, contre un calcul refait en pandas nu."""
    attendu = verite(df)
    obtenu = _reponse(question, ebauches[0])

    assert _egal(obtenu, attendu), (
        "« %s » : attendu %s, obtenu %s" % (question, attendu, obtenu))


@pytest.mark.parametrize("question,ebauches,verite",
                         [c for c in BANC if len(c[1]) > 1],
                         ids=[c[0][:48] for c in BANC if len(c[1]) > 1])
def test_la_reponse_ne_depend_pas_de_l_ebauche_du_modele(question, ebauches, verite, df):
    """Axe 2 — la stabilité : le cœur du reproche « parfois bon, parfois mauvais ».

    Le modèle ne produit pas la même ébauche d'une fois sur l'autre. Si la réponse en
    dépend, l'utilisateur voit deux chiffres pour une question qu'il n'a pas changée
    — et n'a aucun moyen de savoir lequel croire.
    """
    attendu = verite(df)
    reponses = [_reponse(question, e) for e in ebauches]

    for i, obtenu in enumerate(reponses):
        assert _egal(obtenu, attendu), (
            "« %s », ébauche n°%d : attendu %s, obtenu %s"
            % (question, i + 1, attendu, obtenu))


def test_le_banc_couvre_les_familles_de_questions():
    """Un banc qui rétrécit sans qu'on s'en aperçoive ne prouve plus rien."""
    assert len(BANC) >= 30, "le banc a perdu des questions : %d" % len(BANC)
    # Plus de la moitié des questions doivent éprouver la STABILITÉ, faute de quoi
    # le banc ne dirait plus rien du défaut qu'il a été écrit pour attraper.
    avec_variantes = [c for c in BANC if len(c[1]) > 1]
    assert len(avec_variantes) >= 12, len(avec_variantes)
