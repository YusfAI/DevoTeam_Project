from datetime import date

import pytest

from backend import data_store
from backend.data_store import (
    RowError, SHEET_COLUMNS, _nom_canonique, _normalize_choice, _parse_date,
    _parse_float, _parse_row, _parse_win_probability, refresh_dataframe, get_dataframe,
)


# ---------------------------------------------------------------------------
# Fonctions de parsing pures (portées telles quelles depuis l'ancien sheets_sync.py)
# ---------------------------------------------------------------------------

def test_parse_date_iso_format():
    assert _parse_date("2026-12-31", "deadline") == date(2026, 12, 31)


def test_parse_date_french_format():
    assert _parse_date("31/12/2026", "deadline") == date(2026, 12, 31)


def test_parse_date_empty_raises():
    with pytest.raises(RowError, match="deadline"):
        _parse_date("", "deadline")


def test_parse_float_comma_decimal():
    assert _parse_float("1 234,56", "budget") == 1234.56


def test_parse_float_empty_is_none():
    assert _parse_float("", "budget") is None


def test_parse_win_probability_percentage_is_converted():
    assert _parse_win_probability("60") == 0.6


def test_parse_win_probability_out_of_range_raises():
    with pytest.raises(RowError, match="win_probability"):
        _parse_win_probability("150")


def test_normalize_choice_case_insensitive():
    assert _normalize_choice("risk advisory", "practice") == "Risk Advisory"


def test_normalize_choice_invalid_raises():
    with pytest.raises(RowError, match="Risk Advisory"):
        _normalize_choice("Not A Real Practice", "practice")


# ---------------------------------------------------------------------------
# En-têtes d'une vraie feuille métier — pas les noms internes anglais
#
# Le fichier dont ce projet est parti (une feuille déjà en usage réelle) porte ces
# intitulés français. Les imposer à renommer casserait un outil que d'autres
# utilisent déjà pour leur travail quotidien ; _nom_canonique() les reconnaît donc
# en plus des noms internes, sans quoi INTÉGRER LA FEUILLE RÉELLE D'UNE
# UTILISATRICE serait impossible sans qu'elle modifie ses colonnes.
# ---------------------------------------------------------------------------

def test_nom_canonique_reconnait_les_entetes_francais_reels():
    correspondances = {
        "Pays": "country",
        "Date de création": "created_date",
        "Deadline": "deadline",
        "Practice": "practice",
        "Description de la prestation": "description",
        "Lead (Acheteur)": "buyer",
        "Types": "opp_type",
        "Statut": "status",
        "Budget": "budget",
        "Financement": "funding_source",
        "Partenaire": "partner",
        "Offre financière": "financial_offer",
        "Pondéré à": "win_probability",
        # Colonnes calculées : jamais lues, seulement tenues à jour si présentes.
        "Année Deadline": "deadline_year",
        "Jours Rest.": "days_remaining",
        "Pondération": "weighted_amount",
    }
    for entete, attendu in correspondances.items():
        assert _nom_canonique(entete) == attendu, entete


def test_nom_canonique_insensible_a_la_casse():
    # "Practice"/"Budget"/"Deadline" coïncident déjà avec le nom interne — seule la
    # CASSE diffère, et ils ne sont donc pas dans _ALIAS_COLONNES : c'est bien la
    # normalisation qui doit les faire correspondre, pas une entrée de table dédiée.
    assert _nom_canonique("COUNTRY") == "country"
    assert _nom_canonique("Status") == "status"
    assert _nom_canonique("  Budget  ") == "budget"


def test_nom_canonique_ignore_un_entete_inconnu_sans_planter():
    # Ni un nom interne, ni un alias connu : simplement renvoyé tel quel (en
    # minuscules) — il ne correspondra à aucune colonne attendue et sera ignoré,
    # sans faire échouer le chargement pour autant.
    assert _nom_canonique("Colonne Personnalisée") == "colonne personnalisée"


def test_une_feuille_aux_entetes_francais_et_sans_id_se_charge(monkeypatch):
    """Le cas réel : la feuille dont ce projet est parti n'a jamais eu de colonne
    "id" — elle n'en a jamais eu besoin pour son propre usage. Sans la rendre
    facultative AU NIVEAU DE L'EN-TÊTE (pas seulement valeur par valeur), cette
    feuille aurait été rejetée en bloc avec "Colonnes manquantes : id".
    """
    entetes = [
        "Pays", "Date de création", "Deadline", "Horaires Deadline", "Année Deadline",
        "Jours Rest.", "Practice", "Description de la prestation", "Lead (Acheteur)",
        "Types", "Statut", "Budget", "Financement", "Partenaire", "Offre financière",
        "Pondéré à", "Pondération",
    ]
    ligne = ["Bénin", "07/11/2026", "29/12/2026", "15:30", "2026", "154",
             "Digital Transformation", "Elaboration de la stratégie de données",
             "ASIN", "AMI", "Lead", "50000", "ENABEL", "-", "49600", "", ""]
    ws = _FakeWorksheet([entetes, ligne])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    resume = refresh_dataframe()

    assert resume["errors"] == []
    assert resume["total_rows"] == 1
    assert resume["new_ids_assigned"] == 1

    df = get_dataframe()
    assert df.iloc[0]["country"] == "Bénin"
    assert df.iloc[0]["practice"] == "Digital Transformation"
    assert df.iloc[0]["buyer"] == "ASIN"
    assert df.iloc[0]["id"] == 1

    # "Jours Rest." (days_remaining, une colonne CALCULÉE) est bien tenue à jour —
    # ça reste voulu. Ce qui ne doit JAMAIS apparaître, faute de colonne "id" où
    # l'écrire, c'est une tentative d'écriture visant l'identifiant.
    colonnes_ecrites = {col for _, col, _ in ws.update_calls}
    assert entetes.index("Jours Rest.") + 1 in colonnes_ecrites
    assert len(ws.update_calls) == 1  # rien d'autre à réécrire sur cette ligne


def test_une_feuille_francaise_complete_recalcule_le_pondere_correctement():
    """Vérifié contre le fichier réel : la ligne Tunisie/Carrefour porte
    "Offre financière" = 445 400 et "Pondéré à" = 0,8, et sa colonne
    "Pondération" (déjà calculée à la main dans la feuille source) vaut
    356 320 — exactement financial_offer × win_probability. Le recalcul de
    l'application doit retomber sur ce même nombre, preuve que l'alias ne se
    contente pas de faire disparaître l'erreur mais lit la bonne colonne."""
    entetes = [
        "Pays", "Date de création", "Deadline", "Horaires Deadline", "Année Deadline",
        "Jours Rest.", "Practice", "Description de la prestation", "Lead (Acheteur)",
        "Types", "Statut", "Budget", "Financement", "Partenaire", "Offre financière",
        "Pondéré à", "Pondération",
    ]
    ligne = ["Tunisie", "11/10/2026", "26/12/2026", "11:00", "2026", "151",
             "Risk Advisory", "Mise en place d'une PSSI", "Carrefour - UHD",
             "Prospection", "Offre remise", "500000", "Fonds Propres", "FTHM",
             "445400", "0.8", "356320"]
    ws = _FakeWorksheet([entetes, ligne])
    data_store._get_worksheet = lambda: ws
    data_store._cached_df = None
    data_store._last_refresh_summary = {}

    refresh_dataframe()

    df = get_dataframe()
    assert df.iloc[0]["financial_offer"] == 445400.0
    assert df.iloc[0]["win_probability"] == 0.8
    assert df.iloc[0]["weighted_amount"] == 356320.0


def test_une_vraie_colonne_manquante_est_toujours_signalee():
    """L'alias élargit ce qui est RECONNU, il ne rend rien de plus facultatif que
    "id" : une feuille sans l'équivalent d'aucune des deux (ni "country" ni
    "Pays") doit continuer à être refusée, comme avant."""
    entetes_sans_pays = [h for h in SHEET_COLUMNS if h not in ("id", "country")]
    ws = _FakeWorksheet([entetes_sans_pays])
    data_store._get_worksheet = lambda: ws
    data_store._cached_df = None
    data_store._last_refresh_summary = {}

    resume = refresh_dataframe()

    assert resume["errors"]
    assert "country" in resume["errors"][0]


def _row_values(headers, **kwargs):
    return [str(kwargs.get(h, "")) for h in headers]


def _valid_row_kwargs(**overrides):
    base = dict(
        id="", country="France", created_date="2026-01-15", deadline="2026-12-31",
        practice="Risk Advisory", description="Une description", buyer="ACME",
        opp_type="AO", status="Lead", budget="100000", funding_source="Fonds Propres",
        partner="", financial_offer="90000", win_probability="0.6",
    )
    base.update(overrides)
    return base


def test_parse_row_computes_derived_fields():
    row, repairs = _parse_row(SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs()))
    assert row["deadline_month"] == "2026-12"
    assert row["deadline_year"] == 2026
    assert row["weighted_amount"] == 90000 * 0.6
    assert repairs == []  # une ligne saine ne déclenche aucune réparation


def test_parse_row_treats_literal_null_string_as_empty():
    row, _ = _parse_row(
        SHEET_COLUMNS,
        _row_values(SHEET_COLUMNS, **_valid_row_kwargs(partner="NULL", win_probability="NULL")),
    )
    assert row["partner"] is None
    assert row["win_probability"] is None


def test_an_unreadable_cell_costs_the_cell_not_the_row():
    # Rejeter la ligne faisait perdre une opportunité entière — budget, échéance,
    # client — à cause d'un seul statut mal tapé.
    row, repairs = _parse_row(
        SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(status="Statut Bidon")))

    assert row["status"] == data_store.UNKNOWN
    assert row["budget"] == 100000  # le reste de la ligne est intact
    assert [(r["field"], r["value"]) for r in repairs] == [("status", "Statut Bidon")]


def test_a_missing_deadline_empties_the_derived_fields_without_losing_the_row():
    row, repairs = _parse_row(
        SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(deadline="")))

    assert row["deadline"] is None
    assert row["deadline_month"] is None
    assert row["days_remaining"] is None
    # Le budget continue de compter dans les totaux : c'est tout l'intérêt de garder
    # la ligne. Elle sort seulement des analyses temporelles.
    assert row["budget"] == 100000
    assert repairs[0]["field"] == "deadline"


def test_every_repair_is_recorded():
    # Contrepartie non négociable de la tolérance : réparer sans tracer reviendrait
    # à corrompre les données en silence.
    row, repairs = _parse_row(SHEET_COLUMNS, _row_values(
        SHEET_COLUMNS, **_valid_row_kwargs(status="Bidon", practice="Inconnue",
                                            country="", budget="pas un nombre")))

    assert {r["field"] for r in repairs} == {"status", "practice", "country", "budget"}
    assert row["country"] == data_store.UNKNOWN
    assert row["budget"] is None


# ---------------------------------------------------------------------------
# refresh_dataframe() / get_dataframe() — Sheet simulé
# ---------------------------------------------------------------------------

class _FakeWorksheet:
    def __init__(self, values):
        self._values = values
        self.update_calls = []
        self.fail_update = False

    def get_all_values(self):
        return self._values

    def update_cells(self, cell_list, value_input_option=None):
        if self.fail_update:
            raise RuntimeError("network error")
        for cell in cell_list:
            self.update_calls.append((cell.row, cell.col, cell.value))


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    monkeypatch.setattr(data_store, "_cached_df", None)
    monkeypatch.setattr(data_store, "_last_refresh_summary", {})


def test_refresh_assigns_id_to_a_new_row_and_writes_it_back(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id=""))])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["total_rows"] == 1
    assert summary["new_ids_assigned"] == 1
    assert summary["skipped"] == 0
    id_col = SHEET_COLUMNS.index("id") + 1
    written_id = next(v for r, c, v in ws.update_calls if c == id_col)
    df = get_dataframe()
    assert df.iloc[0]["id"] == written_id


def test_refresh_keeps_an_existing_id_unchanged(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="42"))])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["new_ids_assigned"] == 0
    df = get_dataframe()
    assert df.iloc[0]["id"] == 42
    id_col = SHEET_COLUMNS.index("id") + 1
    assert all(c != id_col for _, c, _ in ws.update_calls)  # jamais réécrit, déjà présent


def test_new_id_is_max_existing_plus_one(monkeypatch):
    rows = [
        _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="5")),
        _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="")),
    ]
    ws = _FakeWorksheet([SHEET_COLUMNS, *rows])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    refresh_dataframe()

    df = get_dataframe()
    assert sorted(df["id"].tolist()) == [5, 6]


def test_a_row_with_a_bad_cell_is_repaired_not_dropped(monkeypatch):
    bad_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(status="Statut Bidon"))
    good_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="1"))
    ws = _FakeWorksheet([SHEET_COLUMNS, bad_row, good_row])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["skipped"] == 0
    assert summary["total_rows"] == 2
    # La cellule fautive est nommée avec son numéro de ligne : rien n'est perdu de vue.
    assert summary["repairs"] == [
        {"row": 2, "field": "status", "value": "Statut Bidon", "replacement": data_store.UNKNOWN}
    ]


def test_missing_required_header_aborts_cleanly(monkeypatch):
    incomplete_headers = [h for h in SHEET_COLUMNS if h != "budget"]
    ws = _FakeWorksheet([incomplete_headers])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["errors"]
    assert "budget" in summary["errors"][0]
    assert summary["total_rows"] == 0


def test_empty_sheet_is_a_noop(monkeypatch):
    ws = _FakeWorksheet([])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    # Assertion sur les champs qui portent le sens, pas sur le dict entier :
    # une clé ajoutée au résumé ne doit pas casser un test sur le comportement.
    assert summary["total_rows"] == 0
    assert summary["skipped"] == 0
    assert summary["new_ids_assigned"] == 0
    assert summary["errors"] == []
    df = get_dataframe()
    assert df.empty


def test_completely_blank_row_is_silently_skipped(monkeypatch):
    blank_row = ["" for _ in SHEET_COLUMNS]
    ws = _FakeWorksheet([SHEET_COLUMNS, blank_row])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    # Assertion sur les champs qui portent le sens, pas sur le dict entier :
    # une clé ajoutée au résumé ne doit pas casser un test sur le comportement.
    assert summary["total_rows"] == 0
    assert summary["skipped"] == 0
    assert summary["new_ids_assigned"] == 0
    assert summary["errors"] == []


def test_id_writeback_failure_keeps_the_row_loaded_in_memory(monkeypatch):
    # L'id est déjà attribué en mémoire au moment où l'écriture Sheet échoue — les
    # données restent correctes pour ce chargement, seule la réécriture est perdue.
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id=""))])
    ws.fail_update = True
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["total_rows"] == 1
    assert summary["errors"]
    df = get_dataframe()
    assert len(df) == 1


def test_sheet_read_failure_returns_an_error_without_crashing(monkeypatch):
    def _boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(data_store, "_get_worksheet", _boom)

    summary = refresh_dataframe()

    assert summary["errors"]
    assert summary["total_rows"] == 0


def test_derived_columns_written_back_when_present_in_header(monkeypatch):
    headers = SHEET_COLUMNS + ["deadline_month", "deadline_year", "days_remaining", "weighted_amount"]
    ws = _FakeWorksheet([headers, _row_values(headers, **_valid_row_kwargs(id="1"))])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    refresh_dataframe()

    written_cols = {c for _, c, _ in ws.update_calls}
    dm_col = headers.index("deadline_month") + 1
    assert dm_col in written_cols


def test_derived_columns_not_written_when_absent_from_header(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="1"))])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    refresh_dataframe()

    assert ws.update_calls == []  # rien à réécrire : id déjà présent, pas de colonnes calculées dans l'en-tête


def test_get_dataframe_lazily_loads_on_first_call(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="1"))])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    df = get_dataframe()  # jamais appelé refresh_dataframe() explicitement avant

    assert len(df) == 1


# ---------------------------------------------------------------------------
# Écriture retour : seules les cellules qui changent repartent
# ---------------------------------------------------------------------------

def test_unchanged_derived_columns_are_not_rewritten(monkeypatch):
    """Renvoyer 1 500 cellules identiques à chaque chargement coûtait un aller-retour
    réseau pour rien — mesuré : la synchro passe de ~1 100 ms à ~450 ms."""
    kwargs = _valid_row_kwargs(id="1")
    entetes = SHEET_COLUMNS + list(data_store._DERIVED_SHEET_COLUMNS)

    # Premier passage : les colonnes calculées sont vides, tout doit être écrit.
    ws = _FakeWorksheet([entetes, _row_values(entetes, **kwargs)])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)
    refresh_dataframe()
    ecrites = {c for _, c, _ in ws.update_calls}
    assert ecrites, "les colonnes calculées doivent être écrites la première fois"

    # Second passage : le Sheet porte déjà ce qui vient d'être calculé.
    ligne = dict(kwargs)
    for nom, _, valeur in ws.update_calls:
        ligne[entetes[_ - 1]] = valeur
    ws2 = _FakeWorksheet([entetes, _row_values(entetes, **ligne)])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws2)
    refresh_dataframe()

    assert ws2.update_calls == [], "aucune cellule ne devait repartir"


def test_a_derived_value_that_really_changed_is_still_written(monkeypatch):
    # Le garde-fou de l'autre côté : sauter une écriture nécessaire laisserait une
    # valeur périmée dans le Sheet de l'utilisateur.
    entetes = SHEET_COLUMNS + list(data_store._DERIVED_SHEET_COLUMNS)
    ligne = _valid_row_kwargs(id="1")
    ligne["deadline_month"] = "1999-01"  # volontairement faux

    ws = _FakeWorksheet([entetes, _row_values(entetes, **ligne)])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)
    refresh_dataframe()

    colonne = entetes.index("deadline_month") + 1
    assert any(c == colonne for _, c, _ in ws.update_calls)


def test_a_number_written_differently_is_not_rewritten():
    # Le Sheet rend « 72000 » là où Python écrit « 72000.0 » : une comparaison de
    # texte conclurait à tort qu'il faut réécrire, à chaque chargement.
    assert data_store._valeur_identique("72000", 72000.0)
    assert data_store._valeur_identique("", None)
    assert not data_store._valeur_identique("72000", 72001.0)
    assert not data_store._valeur_identique("", 5)
