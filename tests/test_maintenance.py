from backend import maintenance


class _FakeCursor:
    def __init__(self, capture, affected):
        self._capture = capture
        self._affected = affected

    def execute(self, query, params=None):
        self._capture["query"] = query
        self._capture["params"] = params
        return self._affected

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, capture, affected):
        self._capture = capture
        self._affected = affected
        self.committed = False

    def cursor(self):
        return _FakeCursor(self._capture, self._affected)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_refresh_recomputes_from_live_deadline_not_a_blind_decrement(monkeypatch):
    # A blind "days_remaining - 1" would drift forever the first time the server is
    # down for a day; recomputing from DATEDIFF(deadline, CURDATE()) is self-correcting.
    capture = {}
    monkeypatch.setattr(maintenance, "get_connection", lambda: _FakeConn(capture, 42))

    affected = maintenance.refresh_days_remaining()

    assert "DATEDIFF(deadline, CURDATE())" in capture["query"]
    assert "UPDATE opportunities" in capture["query"]
    assert affected == 42


def test_refresh_commits_the_transaction(monkeypatch):
    capture = {}
    fake_conn = _FakeConn(capture, 1)
    monkeypatch.setattr(maintenance, "get_connection", lambda: fake_conn)

    maintenance.refresh_days_remaining()

    assert fake_conn.committed is True


def test_refresh_survives_a_db_failure(monkeypatch):
    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(maintenance, "get_connection", _boom)

    assert maintenance.refresh_days_remaining() == 0
