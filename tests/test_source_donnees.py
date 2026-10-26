"""« Santé des données » et « Lier une feuille Google » (backend/data_source.py).

Changer de feuille depuis l'interface remplace une étape qui se faisait jusqu'ici
dans une invite de commandes (INSTALLER.bat, étape 5/7). Le risque n'est pas qu'elle
échoue bruyamment, mais qu'elle RÉUSSISSE sur la mauvaise feuille : Google renvoie le
premier onglet sans erreur quand le nom demandé n'existe pas, et une feuille aux
colonnes mal nommées se charge… vide. Ces tests vérifient que chacun de ces cas est
arrêté AVANT que la feuille soit inscrite dans .env — et que l'inscription, elle, ne
touche à rien d'autre dans le fichier.
"""
import os

import pytest
import requests
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from backend import data_source, data_store, main
from backend.data_store import SHEET_COLUMNS, SourceError

LIEN = "https://docs.google.com/spreadsheets/d/1tTAhb78H4nmCWB63cOlMXBgl_L5xh5hUav_ZocyDZfc/edit#gid=222"
IDENTIFIANT = "1tTAhb78H4nmCWB63cOlMXBgl_L5xh5hUav_ZocyDZfc"


def _ligne(**valeurs):
    base = {
        "id": "1", "country": "Maroc", "created_date": "2026-01-10", "deadline": "2026-06-30",
        "practice": "Risk Advisory", "description": "Mission", "buyer": "ONEE",
        "opp_type": "AMI", "status": "Lead", "budget": "100000", "funding_source": "BM",
        "partner": "", "financial_offer": "", "win_probability": "0.5",
    }
    base.update(valeurs)
    return [base[c] for c in SHEET_COLUMNS]


FEUILLE = [SHEET_COLUMNS, _ligne(), _ligne(id="2", country="Tunisie", budget="250000")]


@pytest.fixture
def google(monkeypatch):
    """Une feuille simulée : ses onglets, et ce que renvoie chacun d'eux."""
    etat = {"onglets": [{"name": "opportunities", "gid": "0"}, {"name": "Pipeline 2026", "gid": "222"}],
            "contenu": {"opportunities": FEUILLE, "Pipeline 2026": FEUILLE},
            "lectures": []}

    def lire(sheet_id=None, tab_name=None):
        etat["lectures"].append(tab_name)
        if isinstance(etat["contenu"], Exception):
            raise etat["contenu"]
        # Comme Google : un onglet inconnu renvoie le premier, sans erreur.
        return etat["contenu"].get(tab_name, next(iter(etat["contenu"].values())))

    monkeypatch.setattr(data_source, "lister_onglets", lambda sheet_id: etat["onglets"])
    monkeypatch.setattr(data_source, "fetch_sheet_values", lire)
    return etat


# --- Liste des onglets --------------------------------------------------------

class _Reponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_les_onglets_sont_lus_dans_la_page_publique_de_la_feuille(monkeypatch):
    page = ('items.push({name: "opportunities", pageUrl: "https:\\/\\/docs.google.com\\/x?headers\\x3dtrue&gid=0"});'
            'items.push({name: "Pipeline \\x232", pageUrl: "https:\\/\\/docs.google.com\\/x?gid=1698513051"});')
    monkeypatch.setattr(data_source.requests, "get", lambda *a, **kw: _Reponse(text=page))

    assert data_source.lister_onglets(IDENTIFIANT) == [
        {"name": "opportunities", "gid": "0"},
        {"name": "Pipeline #2", "gid": "1698513051"},
    ]


@pytest.mark.parametrize("reponse", [
    _Reponse(status_code=404),
    _Reponse(text="<html>connexion requise</html>"),  # feuille privée : pas d'onglets
])
def test_sans_liste_lisible_les_onglets_valent_none(monkeypatch, reponse):
    """None, jamais une liste vide : l'interface retombe alors sur un nom saisi."""
    monkeypatch.setattr(data_source.requests, "get", lambda *a, **kw: reponse)
    assert data_source.lister_onglets(IDENTIFIANT) is None


def test_une_panne_reseau_ne_fait_pas_echouer_la_liste(monkeypatch):
    def _panne(*a, **kw):
        raise requests.ConnectionError("hors ligne")
    monkeypatch.setattr(data_source.requests, "get", _panne)
    assert data_source.lister_onglets(IDENTIFIANT) is None


def test_l_onglet_du_lien_colle_est_preselectionne(google):
    """Un lien copié en regardant un onglet porte son gid : c'est celui qu'on veut."""
    reponse = data_source.onglets_de(LIEN)
    assert reponse["onglets"] == ["opportunities", "Pipeline 2026"]
    assert reponse["onglet_du_lien"] == "Pipeline 2026"


def test_un_lien_qui_n_est_pas_une_feuille_est_refuse_avec_le_geste_a_faire():
    reponse = data_source.onglets_de("https://docs.google.com/document/d/abc/edit")
    assert reponse["sheet_id"] is None
    assert "/spreadsheets/d/" in reponse["erreur"]


# --- Diagnostic d'une feuille candidate --------------------------------------

def test_une_feuille_conforme_est_validee_avec_ses_mesures(google):
    diag = data_source.diagnostiquer(LIEN, "opportunities")

    assert diag["statut"] == "ok"
    assert diag["erreur"] is None
    assert diag["source"]["tab"] == "opportunities"
    assert diag["lignes"]["chargees"] == 2
    assert diag["colonnes"]["manquantes"] == []
    assert diag["indicateurs"]["pays"] == 2
    assert diag["indicateurs"]["budget_total"] == 350000
    assert diag["apercu"]["lignes"][0][0] == "Maroc"


def test_sans_onglet_choisi_c_est_celui_du_lien_qui_est_lu(google):
    diag = data_source.diagnostiquer(LIEN, None)
    assert diag["source"]["tab"] == "Pipeline 2026"


def test_un_onglet_inexistant_est_arrete_avant_toute_lecture(google):
    """Le piège principal : Google renverrait le premier onglet, sans erreur."""
    diag = data_source.diagnostiquer(LIEN, "Pipelin 2026")

    assert diag["statut"] == "erreur"
    assert "n'existe pas" in diag["erreur"]
    assert "Pipeline 2026" in diag["erreur"]  # les onglets réels sont proposés
    assert google["lectures"] == []


def test_la_casse_du_nom_d_onglet_est_corrigee_vers_le_nom_exact(google):
    diag = data_source.diagnostiquer(LIEN, "PIPELINE 2026")
    assert diag["statut"] == "ok"
    assert diag["source"]["tab"] == "Pipeline 2026"
    assert google["lectures"] == ["Pipeline 2026"]


def test_des_colonnes_manquantes_bloquent_la_liaison(google):
    sans_pays = [c for c in SHEET_COLUMNS if c != "country"]
    google["contenu"] = {"opportunities": [sans_pays, ["x"] * len(sans_pays)]}

    diag = data_source.diagnostiquer(LIEN, "opportunities")

    assert diag["statut"] == "erreur"
    assert "Pays" in diag["erreur"]
    assert diag["colonnes"]["manquantes"] == ["Pays"]


def test_un_onglet_sans_aucune_ligne_bloque_la_liaison(google):
    google["contenu"] = {"opportunities": [SHEET_COLUMNS]}
    diag = data_source.diagnostiquer(LIEN, "opportunities")
    assert diag["statut"] == "erreur"
    assert "aucune ligne" in diag["erreur"]


def test_une_feuille_non_partagee_donne_le_geste_de_partage(google):
    google["contenu"] = SourceError("pas du CSV", "Google refuse l'accès : Partager › Accès général")
    diag = data_source.diagnostiquer(LIEN, "opportunities")
    assert diag["statut"] == "erreur"
    assert "Partager" in diag["erreur"]


def test_une_cellule_toleree_est_signalee_a_corriger(google):
    google["contenu"] = {"opportunities": [SHEET_COLUMNS, _ligne(status="DP")]}

    diag = data_source.diagnostiquer(LIEN, "opportunities")

    assert diag["statut"] == "attention"
    assert diag["a_corriger"] == [{"ligne": 2, "colonne": "Statut", "valeur": "DP"}]
    # « Des points à vérifier » doit dire lesquels.
    assert diag["avertissements"][0].startswith("1 cellule(s) non reconnue(s)")


def test_sans_liste_d_onglets_le_repli_silencieux_de_google_est_signale(google, monkeypatch):
    """Si Google renvoie pour un onglet impossible la même chose que pour l'onglet
    demandé, c'est que ce dernier est (peut-être) le premier — ou qu'il n'existe pas."""
    monkeypatch.setattr(data_source, "lister_onglets", lambda sheet_id: None)
    diag = data_source.diagnostiquer(LIEN, "Pipelin 2026")

    assert diag["statut"] == "attention"
    assert "PREMIER onglet" in diag["avertissements"][0]


def test_sans_liste_d_onglets_un_onglet_distinct_ne_declenche_pas_d_alerte(google, monkeypatch):
    monkeypatch.setattr(data_source, "lister_onglets", lambda sheet_id: None)
    google["contenu"] = {"premier": [SHEET_COLUMNS, _ligne(country="Bénin")], "Pipeline 2026": FEUILLE}

    diag = data_source.diagnostiquer(LIEN, "Pipeline 2026")

    assert diag["statut"] == "ok"
    assert diag["avertissements"] == []


# --- Inscription dans .env ----------------------------------------------------

ENV_EXISTANT = (
    "# Commentaire d'en-tête\r\n"
    "OLLAMA_HOST=\r\n"
    "GMAIL_APP_PASSWORD=abcdefghijklmnop\r\n"
    "GOOGLE_SHEET_ID=ancien-identifiant\r\n"
    "# GOOGLE_SHEET_TAB=commentaire-a-ne-pas-toucher\r\n"
    "GOOGLE_SHEET_TAB=opportunities\r\n"
)


@pytest.fixture
def env_temporaire(tmp_path, monkeypatch):
    for cle in data_store.SOURCE_KEYS:
        monkeypatch.setenv(cle, "valeur-precedente")  # restaurée par monkeypatch
    return tmp_path / ".env"


def test_seules_les_deux_lignes_de_la_feuille_changent(env_temporaire):
    env_temporaire.write_text(ENV_EXISTANT, encoding="utf-8", newline="")

    data_source.enregistrer_source(IDENTIFIANT, "Pipeline 2026", chemin=env_temporaire)

    octets = env_temporaire.read_bytes()
    assert not octets.startswith(b"\xef\xbb\xbf")  # pas de BOM
    assert octets.count(b"\r\n") == 6               # fins de ligne conservées
    texte = octets.decode("utf-8")
    assert texte == ENV_EXISTANT.replace("ancien-identifiant", IDENTIFIANT).replace(
        "GOOGLE_SHEET_TAB=opportunities", "GOOGLE_SHEET_TAB=Pipeline 2026")


def test_la_feuille_est_mise_en_service_dans_le_processus(env_temporaire):
    data_source.enregistrer_source(IDENTIFIANT, "Pipeline 2026", chemin=env_temporaire)
    assert os.environ["GOOGLE_SHEET_ID"] == IDENTIFIANT
    assert os.environ["GOOGLE_SHEET_TAB"] == "Pipeline 2026"


@pytest.mark.parametrize("onglet", ["Pipeline #2", 'Offres "2026"', " espaces "])
def test_un_nom_d_onglet_delicat_se_relit_a_l_identique(env_temporaire, onglet):
    """Un « # » précédé d'une espace ouvre un commentaire dans .env : sans
    guillemets, la fin du nom d'onglet disparaîtrait en silence."""
    data_source.enregistrer_source(IDENTIFIANT, onglet, chemin=env_temporaire)
    assert dotenv_values(env_temporaire)["GOOGLE_SHEET_TAB"] == onglet


def test_un_env_absent_est_cree(env_temporaire):
    data_source.enregistrer_source(IDENTIFIANT, "opportunities", chemin=env_temporaire)
    assert dotenv_values(env_temporaire) == {
        "GOOGLE_SHEET_ID": IDENTIFIANT, "GOOGLE_SHEET_TAB": "opportunities"}


def test_aucun_fichier_provisoire_ne_reste(env_temporaire):
    data_source.enregistrer_source(IDENTIFIANT, "opportunities", chemin=env_temporaire)
    assert [p.name for p in env_temporaire.parent.iterdir()] == [".env"]


def test_au_demarrage_la_feuille_de_env_prime_sur_l_environnement(env_temporaire, monkeypatch):
    """Sous Docker, l'environnement du conteneur est figé à sa création : sans cette
    priorité, une feuille liée depuis l'interface serait oubliée au redémarrage."""
    env_temporaire.write_text("GOOGLE_SHEET_ID=nouvelle\nGOOGLE_SHEET_TAB=\nOLLAMA_HOST=x\n",
                              encoding="utf-8")
    monkeypatch.setenv("OLLAMA_HOST", "http://host.docker.internal:11434")

    data_store.prendre_la_source_du_fichier_env(env_temporaire)

    assert os.environ["GOOGLE_SHEET_ID"] == "nouvelle"
    assert os.environ["GOOGLE_SHEET_TAB"] == "valeur-precedente"   # vide : ignorée
    assert os.environ["OLLAMA_HOST"] == "http://host.docker.internal:11434"  # jamais touchée


# --- Santé de la feuille en service ------------------------------------------

def test_une_lecture_dit_quand_combien_de_temps_et_quelle_feuille(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEET_ID", LIEN)
    monkeypatch.setenv("GOOGLE_SHEET_TAB", "opportunities")
    monkeypatch.setattr(data_store, "fetch_sheet_values", lambda: FEUILLE)

    summary = data_store.refresh_dataframe()

    assert summary["at"] and summary["duration_ms"] >= 0
    assert summary["source"] == {"sheet_id": IDENTIFIANT, "tab": "opportunities"}
    assert summary["fatal_error"] is None


def test_un_echec_de_lecture_remonte_sa_cause_et_pas_seulement_voir_les_logs(monkeypatch):
    def _privee():
        raise SourceError("pas du CSV", "Google refuse l'accès : partagez la feuille.")
    monkeypatch.setattr(data_store, "fetch_sheet_values", _privee)

    summary = data_store.refresh_dataframe()

    assert summary["fatal_error"] == "Google refuse l'accès : partagez la feuille."
    assert "partagez" in summary["errors"][0]


def test_apres_un_echec_l_etat_dit_que_les_donnees_affichees_datent(monkeypatch):
    monkeypatch.setattr(data_store, "fetch_sheet_values", lambda: FEUILLE)
    data_store.refresh_dataframe()

    def _panne():
        raise requests.ConnectionError("hors ligne")
    monkeypatch.setattr(data_store, "fetch_sheet_values", _panne)
    data_store.refresh_dataframe()

    etat = data_source.etat_actuel()

    assert etat["statut"] == "erreur"
    assert "connexion Internet" in etat["erreur"]
    assert etat["donnees_en_service"] == 2
    assert "lecture précédente" in etat["avertissements"][0]


def test_l_etat_d_une_lecture_reussie(monkeypatch):
    monkeypatch.setattr(data_store, "fetch_sheet_values", lambda: FEUILLE)
    data_store.refresh_dataframe()

    etat = data_source.etat_actuel()

    assert etat["statut"] == "ok"
    assert etat["lignes"]["chargees"] == 2
    assert len(etat["apercu"]["lignes"]) == 2
    assert etat["lecture"]["at"]


# --- Les routes ---------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_dac_is_reachable", lambda: True)
    monkeypatch.setattr(main, "_dac_query_failure", lambda racine=None: None)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def liaison(monkeypatch):
    """Ce que la route de liaison a fait : inscrire, et recharger."""
    appels = {"inscrit": None, "recharge": 0}
    monkeypatch.setattr(main, "enregistrer_source",
                        lambda sheet_id, tab: appels.__setitem__("inscrit", (sheet_id, tab)))

    def _recharger():
        appels["recharge"] += 1
        return {}
    monkeypatch.setattr(main, "_refresh_data", _recharger)
    monkeypatch.setattr(main, "etat_actuel", lambda: {"statut": "ok"})
    return appels


def test_la_sante_des_donnees_inclut_le_moteur_des_tableaux_de_bord(client, monkeypatch):
    monkeypatch.setattr(main, "etat_actuel", lambda: {"statut": "ok"})
    reponse = client.get("/data/source")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok",
                              "tableaux_de_bord": {"ok": True, "repond": True, "detail": None}}


def test_lier_une_feuille_conforme_l_inscrit_et_la_charge(client, liaison, monkeypatch):
    monkeypatch.setattr(main, "diagnostiquer", lambda sheet, tab: {
        "statut": "ok", "erreur": None, "source": {"sheet_id": IDENTIFIANT, "tab": "Pipeline 2026"}})

    reponse = client.post("/data/source", json={"sheet": LIEN, "tab": "pipeline 2026"})

    assert reponse.status_code == 200
    assert liaison["inscrit"] == (IDENTIFIANT, "Pipeline 2026")  # le nom EXACT
    assert liaison["recharge"] == 1


def test_une_feuille_en_erreur_n_est_jamais_inscrite(client, liaison, monkeypatch):
    monkeypatch.setattr(main, "diagnostiquer", lambda sheet, tab: {
        "statut": "erreur", "erreur": "L'onglet « X » n'existe pas.", "source": None})

    reponse = client.post("/data/source", json={"sheet": LIEN, "tab": "X"})

    assert reponse.status_code == 422
    assert "n'existe pas" in reponse.json()["detail"]
    assert liaison["inscrit"] is None
    assert liaison["recharge"] == 0


def test_une_page_d_un_autre_site_ne_peut_pas_changer_la_feuille(client, liaison, monkeypatch):
    monkeypatch.setattr(main, "diagnostiquer", lambda sheet, tab: {
        "statut": "ok", "erreur": None, "source": {"sheet_id": IDENTIFIANT, "tab": "x"}})

    reponse = client.post("/data/source", json={"sheet": LIEN, "tab": "x"},
                          headers={"Origin": "https://site-piege.example"})

    assert reponse.status_code == 403
    assert liaison["inscrit"] is None


@pytest.mark.parametrize("origine", ["http://127.0.0.1:8000", "http://localhost:5173"])
def test_l_interface_de_l_application_peut_changer_la_feuille(client, liaison, monkeypatch, origine):
    monkeypatch.setattr(main, "diagnostiquer", lambda sheet, tab: {
        "statut": "ok", "erreur": None, "source": {"sheet_id": IDENTIFIANT, "tab": "x"}})
    reponse = client.post("/data/source", json={"sheet": LIEN, "tab": "x"},
                          headers={"Origin": origine})
    assert reponse.status_code == 200


def test_tester_une_feuille_ne_change_rien(client, liaison, monkeypatch):
    monkeypatch.setattr(main, "diagnostiquer", lambda sheet, tab: {"statut": "ok", "sheet": sheet, "tab": tab})

    reponse = client.post("/data/source/test", json={"sheet": LIEN, "tab": "opportunities"})

    assert reponse.json() == {"statut": "ok", "sheet": LIEN, "tab": "opportunities"}
    assert liaison["inscrit"] is None and liaison["recharge"] == 0


def test_la_route_des_onglets_relaie_la_liste(client, monkeypatch):
    monkeypatch.setattr(main, "onglets_de", lambda sheet: {"onglets": ["a", "b"], "sheet": sheet})
    reponse = client.post("/data/source/onglets", json={"sheet": LIEN})
    assert reponse.json() == {"onglets": ["a", "b"], "sheet": LIEN}
