"""Le critère des affaires chaudes, sur les deux chemins qui l'appliquent.

Le dashboard le traduit en SQL (widgets de section_chaudes.yml), le chat en opération pandas
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
from tests.test_accueil_dashboard import (
    DASHBOARDS, SECTIONS, COLONNES, _sans_jinja, _widget,
)


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


def _ligne_du_widget(nom):
    """La rangée qui porte ce widget, cherchée dans toutes les sections."""
    for fichier in SECTIONS:
        doc = yaml.safe_load((DASHBOARDS / fichier).read_text(encoding="utf-8"))
        for row in doc["rows"]:
            if any(w["name"] == nom for w in row["widgets"]):
                return row
    raise AssertionError("widget introuvable dans les sections : %r" % nom)


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
    #
    # Statut « Lead » partout : la définition étant une RÉUNION (remise OU ≥ 80 %),
    # laisser le statut par défaut « Offre remise » rendrait les quatre lignes chaudes
    # par ce seul biais, et le test ne prouverait plus rien du seuil.
    df = _df([
        {"buyer": "Presque sûre", "status": "Lead", "win_probability": 0.95},
        {"buyer": "Très probable", "status": "Lead", "win_probability": 0.9},
        {"buyer": "Au seuil", "status": "Lead", "win_probability": HOT_DEAL_MIN_PROBABILITY},
        {"buyer": "Juste en dessous", "status": "Lead", "win_probability": 0.79},
    ])
    assert _kpi_affaires_chaudes(df) == 3


def test_chacun_des_deux_criteres_suffit_a_lui_seul():
    """La définition est une RÉUNION : remise OU ≥ 80 %. L'un suffit.

    Elle a d'abord exigé les deux, puis la seule probabilité, et enfin cette
    réunion — décision métier explicite. Ce test tient les trois cas de figure
    séparés, parce que c'est exactement là que les versions successives diffèrent.
    """
    df = _df([
        # Chaude par la PROBABILITÉ seule : son statut ne la retiendrait pas.
        {"buyer": "Probable", "status": "Lead", "win_probability": 0.95},
        # Chaude par le STATUT seul : sa probabilité ne la retiendrait pas. C'est le
        # cas qu'aucune version précédente ne comptait.
        {"buyer": "Remise tiède", "status": "Offre remise", "win_probability": 0.4},
        # Chaude par les deux.
        {"buyer": "Les deux", "status": "Offre remise", "win_probability": 0.9},
        # Chaude par aucun : la seule qui doit sortir.
        {"buyer": "Ni l'un ni l'autre", "status": "Lead", "win_probability": 0.4},
    ])
    assert _kpi_affaires_chaudes(df) == 3


def test_une_offre_remise_sous_le_seuil_est_chaude(monkeypatch):
    # Le cas qui distingue la définition ACTUELLE de la précédente. Sur les vraies
    # données il n'existe pas encore (les 7 offres remises portent toutes ≥ 80 %),
    # donc seules des lignes fabriquées peuvent le prouver — et sans lui, revenir à
    # l'ancienne règle ne ferait échouer aucun test.
    df = _df([
        {"buyer": "Remise tiède", "status": "Offre remise", "win_probability": 0.3},
    ])
    assert _kpi_affaires_chaudes(df) == 1
    assert _compte_par_le_chat(df, monkeypatch) == 1


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


def _detail_complet(df):
    """Le détail, dans son ordre de lecture."""
    return _duckdb_avec(df).execute(
        _sans_jinja(_widget("Détail des affaires chaudes")["sql"])).fetchall()


def test_le_detail_montre_chaque_affaire_une_fois_et_une_seule():
    """Aucune affaire perdue, aucune en double, dans l'ordre du classement.

    Le détail a été découpé en trois colonnes, puis en deux, tant que la définition
    d'alors en retenait plus d'une centaine ; il tient aujourd'hui dans une table
    unique. La propriété vérifiée ici n'a jamais changé — c'est elle qui rendait
    chaque découpage sûr, et elle reste le garde-fou maintenant qu'il n'y en a plus.
    """
    df = _df([{"buyer": "C%02d" % i, "weighted_amount": float(1000 - i)} for i in range(30)])
    lignes = _detail_complet(df)

    rangs = [l[0] for l in lignes]
    assert len(lignes) == 30
    assert sorted(rangs) == list(range(1, 31))
    # Et l'ordre de lecture suit l'espérance de gain décroissante, colonne après colonne.
    assert [l[2] for l in lignes] == ["C%02d" % i for i in range(30)]


def test_le_detail_occupe_sa_ligne_en_pleine_largeur():
    # Seul sur sa ligne : un widget voisin s'étirerait à la hauteur de la liste. Et
    # en pleine largeur, sans quoi les huit colonnes partiraient en défilement
    # horizontal — le tableau de DAC réclame 400 px au minimum.
    ligne = _ligne_du_widget("Détail des affaires chaudes")

    assert [w["name"] for w in ligne["widgets"]] == ["Détail des affaires chaudes"]
    assert ligne["widgets"][0]["col"] == 12
    # Aucune hauteur : le tableau de DAC ne défile pas verticalement, la borner
    # clipperait les affaires suivantes au lieu de les rendre atteignables.
    assert "height" not in ligne


def test_the_dashboard_and_the_chat_count_the_same_population(monkeypatch):
    # Statuts explicites sur chaque ligne : avec le défaut « Offre remise », les
    # quatre seraient chaudes par le statut et le test ne comparerait plus que ça.
    df = _df([
        {"buyer": "A", "status": "Offre gagnée", "win_probability": 1.0},   # ACQUISE, pas chaude
        {"buyer": "B", "status": "Lead", "win_probability": 0.8},            # chaude (proba)
        {"buyer": "C", "status": "Offre remise", "win_probability": 0.79},   # chaude (statut)
        {"buyer": "D", "status": "Lead", "win_probability": None,
         "weighted_amount": None},                                           # ni l'un ni l'autre
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


def test_le_detail_porte_toutes_les_metriques_de_l_affaire():
    """Le détail ne montrait que rang, opportunité, client et montant pondéré.

    Practice, budget et probabilité en étaient absents — or ce sont eux qui disent
    POURQUOI l'affaire est chaude et ce qu'elle pèse. Sept colonnes ne tenant pas
    dans un tiers de largeur, le détail est passé de trois colonnes à deux moitiés.
    """
    colonnes = [c["name"] for c in _widget("Détail des affaires chaudes")["columns"]]
    for attendue in ("rang", "description", "buyer", "practice", "status", "budget",
                     "win_probability", "weighted_amount"):
        assert attendue in colonnes, f"« {attendue} » manque au détail"


def test_les_parts_rapportent_les_affaires_chaudes_au_portefeuille_actif():
    """Un nombre seul ne dit pas s'il est gros.

    « 105 affaires chaudes » prend un tout autre sens selon qu'il représente 5 % ou
    46 % de ce qui est en jeu. Le dénominateur doit être le portefeuille ACTIF —
    affaires perdues exclues — le même que celui des KPI de santé : le rapporter au
    portefeuille entier gonflerait le dénominateur avec des affaires mortes.
    """
    for nom in ("Part des opportunités", "Part du budget"):
        sql = _widget(nom)["sql"]
        assert "status NOT IN" in sql, f"« {nom} » ne rapporte pas au portefeuille actif"
        assert "NULLIF" in sql, f"« {nom} » divise sans se protéger d'un dénominateur nul"


def test_une_part_vaut_bien_le_rapport_des_deux_kpi():
    # Le chiffre lui-même, sur des lignes fabriquées : 2 chaudes sur 4 actives.
    df = _df([
        {"buyer": "Chaude 1", "status": "Offre remise", "win_probability": 0.9},
        {"buyer": "Chaude 2", "status": "Lead", "win_probability": 0.9},
        {"buyer": "Tiède", "status": "Lead", "win_probability": 0.2},
        {"buyer": "Tiède 2", "status": "Lead", "win_probability": 0.2},
    ])
    con = _duckdb_avec(df)
    part = con.execute(_sans_jinja(_widget("Part des opportunités")["sql"])).fetchall()[0][0]
    assert abs(part - 0.5) < 1e-9, part


def test_une_affaire_a_cent_pour_cent_est_acquise_pas_chaude(monkeypatch):
    """La borne haute, exclue — et la seule chose qui distingue cette définition
    de la précédente.

    Sur les vraies données, 100 % n'est jamais une prévision : les 88 lignes à 1,0
    sont toutes « Offre gagnée » ou « Offre signée ». Les compter faisait passer le
    portefeuille chaud de 9 à 97 opportunités, en y versant l'acquis avec l'à-venir.
    """
    df = _df([
        {"buyer": "Déjà gagnée", "status": "Offre gagnée", "win_probability": 1.0},
        {"buyer": "Déjà signée", "status": "Offre signée", "win_probability": 1.0},
        {"buyer": "À aller chercher", "status": "Lead", "win_probability": 0.99},
    ])
    assert _kpi_affaires_chaudes(df) == 1
    assert _compte_par_le_chat(df, monkeypatch) == 1


def test_les_deux_bornes_sont_verifiees_ensemble(monkeypatch):
    # L'intervalle complet, borne par borne : 0,79 dehors, 0,80 dedans, 0,99 dedans,
    # 1,00 dehors. Chacune des quatre casse une erreur d'inégalité différente.
    df = _df([
        {"buyer": "0.79", "status": "Lead", "win_probability": 0.79},
        {"buyer": "0.80", "status": "Lead", "win_probability": 0.80},
        {"buyer": "0.99", "status": "Lead", "win_probability": 0.99},
        {"buyer": "1.00", "status": "Lead", "win_probability": 1.00},
    ])
    assert _kpi_affaires_chaudes(df) == 2
    assert _compte_par_le_chat(df, monkeypatch) == 2
