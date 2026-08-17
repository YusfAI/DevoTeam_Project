import json
import pytest

from backend import llm


class _FakeGeminiResponse:
    def __init__(self, content):
        self.text = content


def _mock_llm_response(monkeypatch, payload: dict):
    """Force the Gemini path (bypass the rule-based pre-parser) and stub the API response."""
    monkeypatch.setattr(llm, "try_rule_based_parse", lambda query: None)
    monkeypatch.setattr(
        llm.client.models, "generate_content",
        lambda *a, **kw: _FakeGeminiResponse(json.dumps(payload)),
    )


def _mock_db_context(monkeypatch, **ctx):
    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": [], "funding_sources": [], "partners": [], **ctx,
    })


def _base_payload(**overrides):
    payload = {
        "goal": "Test", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    payload.update(overrides)
    return payload


def test_recoverable_metric_synonym_is_mapped(monkeypatch):
    _mock_db_context(monkeypatch)
    _mock_llm_response(monkeypatch, _base_payload(metric="chiffre d'affaires"))
    result = llm.parse_user_query("c'est quoi le chiffre d'affaires ?")
    assert result["metric"] == "budget"
    assert result["is_conversation"] is False


def test_unrecognizable_metric_asks_for_clarification_instead_of_guessing(monkeypatch):
    _mock_db_context(monkeypatch)
    _mock_llm_response(monkeypatch, _base_payload(metric="xyz123"))
    result = llm.parse_user_query("truc bizarre")
    # Must NOT silently fall back to "budget" — must surface a clarification request.
    assert result["is_conversation"] is True
    assert "clarification" in result
    assert result["metric"] == ""


def test_known_country_filter_is_preserved(monkeypatch):
    _mock_db_context(monkeypatch, countries=["France", "Belgique", "Maroc"])
    _mock_llm_response(monkeypatch, _base_payload(filters={"country": "France"}))
    result = llm.parse_user_query("montre les revenus en france stp")
    # Regression test for the filter-dropping bug observed in out.txt: a valid,
    # whitelisted filter value must survive end to end.
    assert result["filters"] == {"country": "France"}


def test_unrecognized_country_value_asks_for_clarification(monkeypatch):
    _mock_db_context(monkeypatch, countries=["France", "Belgique", "Maroc"])
    _mock_llm_response(monkeypatch, _base_payload(filters={"country": "Atlantis"}))
    result = llm.parse_user_query("revenus en atlantis")
    assert result["is_conversation"] is True
    assert "Atlantis" in result["clarification"]


def test_unsupported_filter_key_is_rejected(monkeypatch):
    _mock_db_context(monkeypatch)
    _mock_llm_response(monkeypatch, _base_payload(filters={"region": "EMEA"}))
    with pytest.raises(ValueError):
        llm.parse_user_query("budget en EMEA")


def test_rule_based_path_does_not_silently_drop_an_unrecognized_location(monkeypatch):
    # Regression test: "budget en atlantis" has a metric keyword ("budget") that the
    # offline rule-based parser trusts with high confidence, but that parser has no
    # notion of countries (DB-only data) so it silently produced filters={} — i.e.
    # the response looked like a real answer while quietly ignoring "atlantis".
    # The real try_rule_based_parse runs here (not mocked) so we can verify the
    # guard actually kicks in; only the Gemini call and DB context are stubbed.
    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": ["France", "Belgique"], "funding_sources": [], "partners": [],
    })
    monkeypatch.setattr(
        llm.client.models, "generate_content",
        lambda *a, **kw: _FakeGeminiResponse(json.dumps(_base_payload(
            metric="budget", filters={"country": "Atlantis"}, chart_type="kpi_card",
        ))),
    )
    result = llm.parse_user_query("budget en atlantis")
    # Must NOT silently return the unfiltered rule-based result — must go through
    # the LLM + validation path, which then rejects the unknown country explicitly.
    assert result["is_conversation"] is True
    assert "Atlantis" in result["clarification"]


def test_rule_based_path_still_captures_a_known_country_without_calling_the_llm(monkeypatch):
    def _fail(*a, **kw):
        raise AssertionError("Gemini should not be called when the rule-based path resolves cleanly")

    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": ["France", "Belgique"], "funding_sources": [], "partners": [],
    })
    monkeypatch.setattr(llm.client.models, "generate_content", _fail)

    result = llm.parse_user_query("budget en france")
    assert result["filters"]["country"] == "France"


# --- Comparaisons (filtres à valeurs multiples) ---

def test_comparison_filter_list_is_resolved(monkeypatch):
    _mock_db_context(monkeypatch, countries=["France", "Belgique", "Maroc"])
    _mock_llm_response(monkeypatch, _base_payload(
        dimension="country", chart_type="bar", filters={"country": ["France", "Maroc"]},
    ))
    result = llm.parse_user_query("compare le budget entre la france et le maroc")
    assert result["filters"]["country"] == ["France", "Maroc"]


def test_comparison_filter_with_one_unknown_value_is_rejected(monkeypatch):
    _mock_db_context(monkeypatch, countries=["France", "Belgique", "Maroc"])
    _mock_llm_response(monkeypatch, _base_payload(
        dimension="country", chart_type="bar", filters={"country": ["France", "Atlantis"]},
    ))
    result = llm.parse_user_query("compare la france et atlantis")
    assert result["is_conversation"] is True
    assert "Atlantis" in result["clarification"]


def test_rule_based_path_defers_to_llm_on_comparison_wording(monkeypatch):
    # "compare ... budget" contains the "budget" keyword the fast path trusts, but a
    # comparison needs a list-valued filter the fast path can never produce — it must
    # not silently return a single-country (or unfiltered) result.
    def _fail(*a, **kw):
        raise AssertionError("should not resolve via the offline fast path")

    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": ["France", "Maroc"], "funding_sources": [], "partners": [],
    })
    called = {}

    def _create(*a, **kw):
        called["yes"] = True
        return _FakeGeminiResponse(json.dumps(_base_payload(
            dimension="country", chart_type="bar", filters={"country": ["France", "Maroc"]},
        )))

    monkeypatch.setattr(llm.client.models, "generate_content", _create)
    llm.parse_user_query("compare le budget France vs Maroc")
    assert called.get("yes") is True


def test_rule_based_path_defers_to_llm_when_multiple_countries_named(monkeypatch):
    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": ["France", "Maroc"], "funding_sources": [], "partners": [],
    })
    called = {}

    def _create(*a, **kw):
        called["yes"] = True
        return _FakeGeminiResponse(json.dumps(_base_payload(
            dimension="country", chart_type="bar", filters={"country": ["France", "Maroc"]},
        )))

    monkeypatch.setattr(llm.client.models, "generate_content", _create)
    llm.parse_user_query("budget france et maroc")
    assert called.get("yes") is True


# --- Contexte multi-tour ---

def test_previous_intent_skips_the_fast_path_and_reaches_gemini(monkeypatch):
    # Even a query that would normally resolve via the offline fast path ("budget
    # par pays") must go through the LLM once there's conversational context to
    # interpret, since the fast path has no notion of context.
    monkeypatch.setattr(llm, "_load_db_context", lambda: {
        "countries": [], "funding_sources": [], "partners": [],
    })
    captured = {}

    def _create(*, model, contents, config):
        captured["system_prompt"] = config.system_instruction
        return _FakeGeminiResponse(json.dumps(_base_payload(
            dimension="country", chart_type="bar", filters={"practice": "Data Management"},
        )))

    monkeypatch.setattr(llm.client.models, "generate_content", _create)
    previous = {
        "goal": "Budget par pays — Risk Advisory", "metric": "budget", "dimension": "country",
        "filters": {"practice": "Risk Advisory"}, "chart_type": "bar", "aggregation": "sum",
        "range_filters": {}, "use_raw_table": False,
    }
    result = llm.parse_user_query("et pour Data Management ?", previous_intent=previous)
    assert "system_prompt" in captured
    assert "Risk Advisory" in captured["system_prompt"]
    assert "CONTEXTE" in captured["system_prompt"]
    assert result["filters"]["practice"] == "Data Management"


def test_no_previous_intent_still_uses_fast_path(monkeypatch):
    def _fail(*a, **kw):
        raise AssertionError("Gemini should not be called when there is no context and the fast path resolves")

    monkeypatch.setattr(llm.client.models, "generate_content", _fail)
    result = llm.parse_user_query("budget par pays pour Risk Advisory")
    assert result["filters"]["practice"] == "Risk Advisory"


def test_degraded_db_context_accepts_value_without_blocking(monkeypatch):
    # DB unreachable -> live country list is empty; the app should not block every
    # country-filtered query just because the reference list couldn't be loaded.
    _mock_db_context(monkeypatch, countries=[])
    _mock_llm_response(monkeypatch, _base_payload(filters={"country": "France"}))
    result = llm.parse_user_query("revenus en france")
    assert result["filters"] == {"country": "France"}
