from datetime import date
from email import message_from_string

import pandas as pd
import pytest

from backend import alerts


def _row(**overrides):
    base = dict(
        id=1, country="Maroc", created_date=date(2026, 1, 1), deadline=date(2026, 8, 10),
        deadline_month="2026-08", deadline_year=2026, days_remaining=3,
        practice="Risk Advisory", description=None, buyer="ACME", opp_type="AO",
        status="Offre remise", budget=50000.0, funding_source=None,
        partner=None, financial_offer=None, win_probability=None, weighted_amount=None,
    )
    base.update(overrides)
    return base


def test_query_excludes_closed_statuses_and_filters_on_the_live_days_remaining(monkeypatch):
    # days_remaining is recomputed at every DataFrame load (data_store.py) from the
    # real deadline — never a value that could go stale, unlike a value frozen at
    # import time.
    rows = [
        _row(id=1, status="Offre remise", days_remaining=3),          # actif, dans la fenêtre -> gardé
        _row(id=2, status="Offre gagnée", days_remaining=2),          # clos -> exclu malgré l'échéance proche
        _row(id=3, status="Lead", days_remaining=30),                 # hors fenêtre -> exclu
        _row(id=4, status="Lead", days_remaining=-1),                 # déjà dépassée -> exclue (borne 0..N)
    ]
    df = pd.DataFrame(rows)
    monkeypatch.setattr(alerts, "get_dataframe", lambda: df)

    result = alerts.get_upcoming_deadline_opportunities()

    assert [r["id"] for r in result] == [1]
    assert result[0]["days_left"] == 3


def test_run_daily_alert_check_sends_nothing_when_no_opportunity_is_at_risk(monkeypatch):
    monkeypatch.setattr(alerts, "get_dataframe", lambda: pd.DataFrame(columns=list(_row().keys())))
    sent = {"called": False}
    monkeypatch.setattr(alerts, "send_alert_email", lambda opps: sent.__setitem__("called", True))

    count = alerts.run_daily_alert_check()

    assert count == 0
    assert sent["called"] is False


def test_run_daily_alert_check_sends_digest_for_at_risk_opportunities(monkeypatch):
    df = pd.DataFrame([_row(id=1, country="Maroc", buyer="ACME", status="Offre remise", days_remaining=3)])
    monkeypatch.setattr(alerts, "get_dataframe", lambda: df)
    sent = {}
    monkeypatch.setattr(alerts, "send_alert_email", lambda opps: sent.setdefault("opportunities", opps))

    count = alerts.run_daily_alert_check()

    assert count == 1
    assert sent["opportunities"][0]["buyer"] == "ACME"


def test_run_daily_alert_check_survives_a_read_failure(monkeypatch):
    def _boom():
        raise RuntimeError("Sheet indisponible")

    monkeypatch.setattr(alerts, "get_dataframe", _boom)

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
# Rattrapage du scheduler (run_daily_alert_check_if_needed) — fichier JSON local
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler_state_path(tmp_path, monkeypatch):
    path = tmp_path / "scheduler_state.json"
    monkeypatch.setattr(alerts, "_SCHEDULER_STATE_PATH", path)
    return path


def test_already_ran_today_is_false_with_no_prior_record(scheduler_state_path):
    assert alerts._already_ran_today("daily_deadline_alert") is False


def test_mark_ran_today_makes_already_ran_today_true(scheduler_state_path):
    alerts._mark_ran_today("daily_deadline_alert")
    assert alerts._already_ran_today("daily_deadline_alert") is True


def test_already_ran_today_is_false_for_a_stale_previous_day(scheduler_state_path):
    scheduler_state_path.parent.mkdir(parents=True, exist_ok=True)
    scheduler_state_path.write_text('{"daily_deadline_alert": "2020-01-01"}', encoding="utf-8")
    assert alerts._already_ran_today("daily_deadline_alert") is False


def test_run_daily_alert_check_if_needed_skips_a_second_call_same_day(scheduler_state_path, monkeypatch):
    # This is the catch-up guarantee: whether triggered by the 8h cron or by a late
    # server startup, the digest is never sent twice for the same calendar day.
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
        raise RuntimeError("fichier illisible")

    monkeypatch.setattr(alerts, "_already_ran_today", _boom)
    monkeypatch.setattr(alerts, "_mark_ran_today", lambda job_name: None)
    calls = []
    monkeypatch.setattr(alerts, "run_daily_alert_check", lambda: calls.append(1) or 5)

    result = alerts.run_daily_alert_check_if_needed()

    assert result == 5
    assert len(calls) == 1
