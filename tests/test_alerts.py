from datetime import date
from email import message_from_string

from backend import alerts


class _FakeCursor:
    def __init__(self, capture, rows):
        self._capture = capture
        self._rows = rows

    def execute(self, query, params=None):
        self._capture["query"] = query
        self._capture["params"] = params

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, capture, rows):
        self._capture = capture
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._capture, self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_query_excludes_closed_statuses_and_filters_on_live_datediff(monkeypatch):
    # days_remaining is a value frozen at data import time — the alert must compute
    # the window against today's real date via DATEDIFF(deadline, CURDATE()), never
    # trust the stored column, or it would drift as soon as "today" moves on.
    capture = {}
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeConn(capture, []))

    alerts.get_upcoming_deadline_opportunities()

    query = capture["query"]
    assert "DATEDIFF(deadline, CURDATE())" in query
    assert "days_remaining" not in query
    assert capture["params"][0] == alerts.ALERT_WINDOW_DAYS
    assert capture["params"][1:] == tuple(alerts.EXCLUDED_STATUSES)


def test_run_daily_alert_check_sends_nothing_when_no_opportunity_is_at_risk(monkeypatch):
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeConn({}, []))
    sent = {"called": False}
    monkeypatch.setattr(alerts, "send_alert_email", lambda opps: sent.__setitem__("called", True))

    count = alerts.run_daily_alert_check()

    assert count == 0
    assert sent["called"] is False


def test_run_daily_alert_check_sends_digest_for_at_risk_opportunities(monkeypatch):
    rows = [
        {
            "id": 1, "country": "Maroc", "practice": "Risk Advisory", "buyer": "ACME",
            "status": "Offre remise", "deadline": "2026-08-10", "budget": 50000, "days_left": 3,
        },
    ]
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeConn({}, rows))
    sent = {}
    monkeypatch.setattr(alerts, "send_alert_email", lambda opps: sent.setdefault("opportunities", opps))

    count = alerts.run_daily_alert_check()

    assert count == 1
    assert sent["opportunities"] == rows


def test_run_daily_alert_check_survives_a_db_failure(monkeypatch):
    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(alerts, "get_connection", _boom)

    assert alerts.run_daily_alert_check() == 0


def test_send_alert_email_skips_silently_when_config_is_missing(monkeypatch):
    monkeypatch.delenv("GMAIL_SENDER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("ALERT_RECIPIENT_EMAIL", raising=False)

    calls = []
    monkeypatch.setattr(alerts.smtplib, "SMTP", lambda *a, **k: calls.append((a, k)))

    alerts.send_alert_email([{"id": 1, "country": "Maroc", "practice": "RA", "buyer": "ACME",
                               "status": "Offre remise", "deadline": "2026-08-10",
                               "budget": 1000, "days_left": 3}])

    assert calls == []


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        _FakeSMTP.instances.append(self)

    def starttls(self):
        self.started_tls = True

    def login(self, sender, password):
        self.logged_in = (sender, password)

    def sendmail(self, sender, recipients, message):
        self.sent = (sender, recipients, message)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_send_alert_email_uses_gmail_smtp_with_starttls_and_app_password(monkeypatch):
    monkeypatch.setenv("GMAIL_SENDER", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@example.com")
    _FakeSMTP.instances = []
    monkeypatch.setattr(alerts.smtplib, "SMTP", _FakeSMTP)

    opportunities = [{
        "id": 1, "country": "Maroc", "practice": "Risk Advisory", "buyer": "ACME",
        "status": "Offre remise", "deadline": "2026-08-10", "budget": 50000, "days_left": 3,
    }]
    alerts.send_alert_email(opportunities)

    smtp = _FakeSMTP.instances[0]
    assert smtp.host == alerts.SMTP_HOST
    assert smtp.port == alerts.SMTP_PORT
    assert smtp.started_tls is True
    assert smtp.logged_in == ("sender@gmail.com", "abcd efgh ijkl mnop")
    sender, recipients, raw_message = smtp.sent
    assert sender == "sender@gmail.com"
    assert recipients == ["recipient@example.com"]
    parsed = message_from_string(raw_message)
    body = parsed.get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert "ACME" in body
    assert "Maroc" in body


def test_excluded_statuses_cover_won_lost_and_dropped_deals():
    # A regression here would silently start emailing about closed deals every day.
    for status in ("Offre gagnée", "Offre perdue", "Offre signée", "Infructueux",
                    "NO GO", "Hors scope", "Non shortlisté"):
        assert status in alerts.EXCLUDED_STATUSES


# ---------------------------------------------------------------------------
# Rattrapage du scheduler (run_daily_alert_check_if_needed)
# ---------------------------------------------------------------------------

class _FakeSchedulerCursor:
    """Simule scheduler_state comme un dict {job_name: last_run_date} partagé entre
    connexions successives (get_connection() est appelé une fois par fonction)."""

    def __init__(self, state):
        self._state = state
        self._last_result = None

    def execute(self, query, params=None):
        q = query.strip()
        if q.startswith("SELECT last_run_date"):
            job_name = params[0]
            self._last_result = (
                {"last_run_date": self._state[job_name]} if job_name in self._state else None
            )
        elif q.startswith("INSERT INTO scheduler_state"):
            job_name, run_date = params
            self._state[job_name] = run_date
        # CREATE TABLE IF NOT EXISTS : rien à simuler.

    def fetchone(self):
        return self._last_result

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSchedulerConn:
    def __init__(self, state):
        self._state = state

    def cursor(self):
        return _FakeSchedulerCursor(self._state)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_already_ran_today_is_false_with_no_prior_record(monkeypatch):
    state = {}
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeSchedulerConn(state))
    assert alerts._already_ran_today("daily_deadline_alert") is False


def test_mark_ran_today_makes_already_ran_today_true(monkeypatch):
    state = {}
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeSchedulerConn(state))
    alerts._mark_ran_today("daily_deadline_alert")
    assert alerts._already_ran_today("daily_deadline_alert") is True


def test_already_ran_today_is_false_for_a_stale_previous_day(monkeypatch):
    state = {"daily_deadline_alert": date(2020, 1, 1)}
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeSchedulerConn(state))
    assert alerts._already_ran_today("daily_deadline_alert") is False


def test_run_daily_alert_check_if_needed_skips_a_second_call_same_day(monkeypatch):
    # This is the catch-up guarantee: whether triggered by the 8h cron or by a late
    # server startup, the digest is never sent twice for the same calendar day.
    state = {}
    monkeypatch.setattr(alerts, "get_connection", lambda: _FakeSchedulerConn(state))
    calls = []
    monkeypatch.setattr(alerts, "run_daily_alert_check", lambda: calls.append(1) or 3)

    first = alerts.run_daily_alert_check_if_needed()
    second = alerts.run_daily_alert_check_if_needed()

    assert first == 3
    assert second == 0
    assert len(calls) == 1


def test_run_daily_alert_check_if_needed_still_runs_if_the_tracking_check_itself_fails(monkeypatch):
    # A broken anti-duplicate check must never silently swallow the alert entirely.
    def _boom(job_name):
        raise RuntimeError("db down")

    monkeypatch.setattr(alerts, "_already_ran_today", _boom)
    monkeypatch.setattr(alerts, "_mark_ran_today", lambda job_name: None)
    calls = []
    monkeypatch.setattr(alerts, "run_daily_alert_check", lambda: calls.append(1) or 5)

    result = alerts.run_daily_alert_check_if_needed()

    assert result == 5
    assert len(calls) == 1
