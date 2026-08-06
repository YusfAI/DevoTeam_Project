from backend import db_layer


def test_dimension_without_dedicated_view_falls_back_to_opportunities():
    # deadline_year/opp_type have no pre-aggregated view; must resolve explicitly to
    # "opportunities" (triggering the grouped fallback) rather than a phantom view name.
    assert db_layer._compute_target_table("deadline_year", {}) == "opportunities"
    assert db_layer._compute_target_table("opp_type", {}) == "opportunities"


def test_country_practice_cross_filter_uses_combined_view():
    assert db_layer._compute_target_table("country", {"practice": "Risk Advisory"}) == "v_by_country_practice"
    assert db_layer._compute_target_table("practice", {"country": "France"}) == "v_by_country_practice"


def test_simple_dimension_uses_its_own_view():
    assert db_layer._compute_target_table("status", {}) == "v_by_status"
    assert db_layer._compute_target_table("country", {}) == "v_by_country"


class _FakeCursor:
    def __init__(self, capture):
        self._capture = capture

    def execute(self, query, params=None):
        self._capture["query"] = query
        self._capture["params"] = params

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, capture):
        self._capture = capture

    def cursor(self):
        return _FakeCursor(self._capture)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_metric_unavailable_on_view_falls_back_to_grouped_query_instead_of_raising(monkeypatch):
    # v_by_status has no total_weighted column. Previously this raised a ValueError;
    # it should now transparently fall back to a live GROUP BY on opportunities.
    capture = {}
    monkeypatch.setattr(db_layer, "get_connection", lambda: _FakeConn(capture))

    intent = {"dimension": "status", "metric": "weighted_amount", "filters": {}, "range_filters": {}}
    db_layer.build_and_execute_query(intent)

    assert "GROUP BY status" in capture["query"]
    assert "opportunities" in capture["query"]


def test_view_path_used_when_metric_and_filters_are_supported(monkeypatch):
    capture = {}
    monkeypatch.setattr(db_layer, "get_connection", lambda: _FakeConn(capture))

    intent = {"dimension": "country", "metric": "budget", "filters": {}, "range_filters": {}}
    db_layer.build_and_execute_query(intent)

    assert "FROM v_by_country" in capture["query"]


def test_list_valued_filter_becomes_in_clause(monkeypatch):
    capture = {}
    monkeypatch.setattr(db_layer, "get_connection", lambda: _FakeConn(capture))

    intent = {
        "dimension": "country", "metric": "budget",
        "filters": {"country": ["France", "Maroc"]}, "range_filters": {},
    }
    db_layer.build_and_execute_query(intent)

    assert "country IN (%s, %s)" in capture["query"]
    assert capture["params"] == ("France", "Maroc")


def test_between_range_filter_produces_between_clause(monkeypatch):
    capture = {}
    monkeypatch.setattr(db_layer, "get_connection", lambda: _FakeConn(capture))

    intent = {
        "dimension": "", "metric": "budget", "filters": {},
        "range_filters": {"deadline_month": {"op": "between", "value": ["2026-07", "2026-09"]}},
    }
    db_layer.build_and_execute_query(intent)

    assert "deadline_month BETWEEN %s AND %s" in capture["query"]
    assert capture["params"] == ("2026-07", "2026-09")
