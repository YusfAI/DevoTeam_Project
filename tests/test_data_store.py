from datetime import date

import pytest

from backend import data_store
from backend.data_store import (
    RowError, SHEET_COLUMNS, _normalize_choice, _parse_date, _parse_float,
    _parse_row, _parse_win_probability, refresh_dataframe, get_dataframe,
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
    row = _parse_row(SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs()))
    assert row["deadline_month"] == "2026-12"
    assert row["deadline_year"] == 2026
    assert row["weighted_amount"] == 90000 * 0.6


def test_parse_row_treats_literal_null_string_as_empty():
    row = _parse_row(
        SHEET_COLUMNS,
        _row_values(SHEET_COLUMNS, **_valid_row_kwargs(partner="NULL", win_probability="NULL")),
    )
    assert row["partner"] is None
    assert row["win_probability"] is None


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


def test_invalid_row_is_skipped_but_others_still_load(monkeypatch):
    bad_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(status="Statut Bidon"))
    good_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="1"))
    ws = _FakeWorksheet([SHEET_COLUMNS, bad_row, good_row])
    monkeypatch.setattr(data_store, "_get_worksheet", lambda: ws)

    summary = refresh_dataframe()

    assert summary["skipped"] == 1
    assert summary["total_rows"] == 1
    assert "Ligne 2" in summary["errors"][0]


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
