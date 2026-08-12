from datetime import date

import pytest

from backend import sheets_sync
from backend.sheets_sync import (
    RowError, SHEET_COLUMNS, _UPSERT_COLUMNS, _normalize_choice, _parse_date,
    _parse_float, _parse_row, _parse_win_probability, sync_sheet_to_mysql,
)


# ---------------------------------------------------------------------------
# Fonctions de parsing pures
# ---------------------------------------------------------------------------

def test_parse_date_iso_format():
    assert _parse_date("2026-12-31", "deadline") == date(2026, 12, 31)


def test_parse_date_french_format():
    assert _parse_date("31/12/2026", "deadline") == date(2026, 12, 31)


def test_parse_date_empty_raises():
    with pytest.raises(RowError, match="deadline"):
        _parse_date("", "deadline")


def test_parse_date_unrecognized_format_raises():
    with pytest.raises(RowError, match="deadline"):
        _parse_date("31 décembre 2026", "deadline")


def test_parse_float_plain():
    assert _parse_float("100000", "budget") == 100000.0


def test_parse_float_comma_decimal():
    assert _parse_float("1 234,56", "budget") == 1234.56


def test_parse_float_empty_is_none():
    assert _parse_float("", "budget") is None


def test_parse_float_invalid_raises():
    with pytest.raises(RowError, match="budget"):
        _parse_float("abc", "budget")


def test_parse_win_probability_fraction_kept_as_is():
    assert _parse_win_probability("0.6") == 0.6


def test_parse_win_probability_percentage_is_converted():
    # A human typing "60" almost certainly means 60%, not a 6000% probability.
    assert _parse_win_probability("60") == 0.6


def test_parse_win_probability_empty_is_none():
    assert _parse_win_probability("") is None


def test_parse_win_probability_out_of_range_raises():
    with pytest.raises(RowError, match="win_probability"):
        _parse_win_probability("150")


def test_normalize_choice_exact_match():
    assert _normalize_choice("Risk Advisory", "practice") == "Risk Advisory"


def test_normalize_choice_case_insensitive():
    assert _normalize_choice("risk advisory", "practice") == "Risk Advisory"


def test_normalize_choice_invalid_raises_and_lists_allowed_values():
    with pytest.raises(RowError, match="Risk Advisory"):
        _normalize_choice("Not A Real Practice", "practice")


def test_normalize_choice_empty_raises():
    with pytest.raises(RowError, match="practice"):
        _normalize_choice("", "practice")


# ---------------------------------------------------------------------------
# _parse_row — champs dérivés
# ---------------------------------------------------------------------------

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
    assert row["days_remaining"] == (date(2026, 12, 31) - date.today()).days


def test_parse_row_weighted_amount_is_none_without_financial_offer():
    row = _parse_row(SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(financial_offer="")))
    assert row["weighted_amount"] is None


def test_parse_row_missing_country_raises():
    with pytest.raises(RowError, match="country"):
        _parse_row(SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(country="")))


def test_parse_row_treats_literal_null_string_as_empty():
    # The CSV export -> Sheets import writes MySQL NULLs as the literal text "NULL"
    # in some columns, not an empty cell — must not be stored as that literal string.
    row = _parse_row(
        SHEET_COLUMNS,
        _row_values(SHEET_COLUMNS, **_valid_row_kwargs(
            partner="NULL", win_probability="NULL", financial_offer="null",
        )),
    )
    assert row["partner"] is None
    assert row["win_probability"] is None
    assert row["financial_offer"] is None
    assert row["weighted_amount"] is None


# ---------------------------------------------------------------------------
# sync_sheet_to_mysql — orchestration (Sheet + DB simulés)
# ---------------------------------------------------------------------------

class _FakeWorksheet:
    def __init__(self, values):
        self._values = values
        self.update_calls = []
        self.fail_update = False

    def get_all_values(self):
        return self._values

    def update_cell(self, row, col, value):
        if self.fail_update:
            raise RuntimeError("network error")
        self.update_calls.append((row, col, value))


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self.lastrowid = None
        self.rowcount = 0
        self._last_select = None

    def execute(self, query, params=None):
        self.state["queries"].append((query, params))
        q = query.strip()
        if q.startswith("SELECT id FROM opportunities"):
            self._last_select = [{"id": i} for i in self.state["known_ids"]]
        elif q.startswith("INSERT"):
            self.lastrowid = self.state["next_lastrowid"]
            self.state["next_lastrowid"] += 1
        # UPDATE : rowcount volontairement pas simulé de façon fiable ici — le vrai
        # code ne s'y fie plus (voir _update_opportunity), donc les tests ne doivent
        # pas en dépendre non plus.

    def fetchall(self):
        return self._last_select or []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, state):
        self.state = state
        self.committed = False

    def cursor(self):
        return _FakeCursor(self.state)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_db(monkeypatch, known_ids=(), next_lastrowid=500):
    state = {"queries": [], "next_lastrowid": next_lastrowid, "known_ids": set(known_ids)}
    monkeypatch.setattr(sheets_sync, "get_connection", lambda: _FakeConn(state))
    return state


def test_sync_inserts_new_row_and_writes_back_id(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id=""))])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    state = _patch_db(monkeypatch, next_lastrowid=777)

    summary = sync_sheet_to_mysql()

    assert summary == {"inserted": 1, "updated": 0, "skipped": 0, "errors": []}
    id_col = SHEET_COLUMNS.index("id") + 1
    assert ws.update_calls == [(2, id_col, 777)]
    insert_query, insert_params = next(
        (q, p) for q, p in state["queries"] if q.strip().startswith("INSERT")
    )
    assert insert_params[_UPSERT_COLUMNS.index("country")] == "France"


def test_sync_updates_existing_row_by_id(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="7"))])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    state = _patch_db(monkeypatch, known_ids={7})

    summary = sync_sheet_to_mysql()

    assert summary == {"inserted": 0, "updated": 1, "skipped": 0, "errors": []}
    assert ws.update_calls == []  # id already known, nothing to write back
    update_query, update_params = next(
        (q, p) for q, p in state["queries"] if q.strip().startswith("UPDATE")
    )
    assert update_params[-1] == 7


def test_sync_skips_a_row_with_an_unknown_id(monkeypatch):
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id="999"))])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    _patch_db(monkeypatch, known_ids={7})

    summary = sync_sheet_to_mysql()

    assert summary["inserted"] == 0
    assert summary["updated"] == 0
    assert summary["skipped"] == 1
    assert "999" in summary["errors"][0]


def test_sync_skips_invalid_row_but_still_processes_the_rest(monkeypatch):
    bad_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(status="Statut Bidon"))
    good_row = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id=""))
    ws = _FakeWorksheet([SHEET_COLUMNS, bad_row, good_row])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    _patch_db(monkeypatch)

    summary = sync_sheet_to_mysql()

    assert summary["skipped"] == 1
    assert summary["inserted"] == 1
    assert "Ligne 2" in summary["errors"][0]


def test_sync_win_probability_percentage_and_fraction_both_land_the_same(monkeypatch):
    row_fraction = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(win_probability="0.6"))
    row_percent = _row_values(SHEET_COLUMNS, **_valid_row_kwargs(win_probability="60"))
    ws = _FakeWorksheet([SHEET_COLUMNS, row_fraction, row_percent])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    state = _patch_db(monkeypatch)

    sync_sheet_to_mysql()

    wp_idx = _UPSERT_COLUMNS.index("win_probability")
    values = [
        params[wp_idx] for q, params in state["queries"]
        if q.strip().startswith(("INSERT", "UPDATE"))
    ]
    assert values == [0.6, 0.6]


def test_sync_aborts_cleanly_when_a_required_column_is_missing(monkeypatch):
    incomplete_headers = [h for h in SHEET_COLUMNS if h != "budget"]
    ws = _FakeWorksheet([incomplete_headers])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    state = _patch_db(monkeypatch)

    summary = sync_sheet_to_mysql()

    assert summary["errors"]
    assert "budget" in summary["errors"][0]
    assert state["queries"] == []  # never touched the DB


def test_sync_empty_sheet_is_a_noop(monkeypatch):
    ws = _FakeWorksheet([])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    _patch_db(monkeypatch)

    summary = sync_sheet_to_mysql()

    assert summary == {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}


def test_sync_completely_blank_row_is_silently_skipped(monkeypatch):
    blank_row = ["" for _ in SHEET_COLUMNS]
    ws = _FakeWorksheet([SHEET_COLUMNS, blank_row])
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    _patch_db(monkeypatch)

    summary = sync_sheet_to_mysql()

    assert summary == {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}


def test_sync_records_an_error_if_id_writeback_fails_but_keeps_the_insert(monkeypatch):
    # The MySQL insert already succeeded — losing the id writeback is a real risk of
    # a duplicate next run, so it must be loud, but must not undo the insert itself.
    ws = _FakeWorksheet([SHEET_COLUMNS, _row_values(SHEET_COLUMNS, **_valid_row_kwargs(id=""))])
    ws.fail_update = True
    monkeypatch.setattr(sheets_sync, "_get_worksheet", lambda: ws)
    _patch_db(monkeypatch)

    summary = sync_sheet_to_mysql()

    assert summary["inserted"] == 1
    assert summary["errors"]


def test_sync_survives_a_sheet_read_failure(monkeypatch):
    def _boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(sheets_sync, "_get_worksheet", _boom)

    summary = sync_sheet_to_mysql()

    assert summary["inserted"] == 0
    assert summary["errors"]
