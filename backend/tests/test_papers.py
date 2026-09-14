from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app import truth, validator
from app.llm import FakeClient
from app.main import app
from app.scenarios.papers import PAPER_SCENARIOS

client = TestClient(app)


def test_paper_scenarios_validate_and_have_metadata() -> None:
    ids = [scenario.id for scenario in PAPER_SCENARIOS]
    assert len(ids) == len(set(ids))
    for scenario in PAPER_SCENARIOS:
        assert scenario.is_sample is True
        assert scenario.source.kind == "paper"
        assert scenario.source.paper
        assert scenario.source.doi_or_url
        assert scenario.source.fidelity
        assert scenario.source.notes and "approx." in scenario.source.notes
        assert scenario.model_validate(scenario.model_dump())
        for fact in scenario.facts:
            assert fact.memo_text
            assert 2 <= len(fact.keywords) <= 3
            assert all(keyword == keyword.lower() for keyword in fact.keywords)
            assert all(keyword in fact.text.lower() for keyword in fact.keywords)


def test_stasser_1985_arithmetic() -> None:
    scenario = next(s for s in PAPER_SCENARIOS if s.id == "stasser-1985-hidden")
    result = truth.analysis(scenario)
    assert [lean.verdict for lean in result.agent_leans] == ["b"] * 4
    assert result.shared_only_verdict == "b"
    assert result.pooled_verdict == "a"
    assert result.is_hidden_profile is True


def test_stasser_1985_shared_is_not_hidden() -> None:
    scenario = next(s for s in PAPER_SCENARIOS if s.id == "stasser-1985-shared")
    result = truth.analysis(scenario)
    assert result.shared_only_verdict == result.pooled_verdict == "a"
    assert result.is_hidden_profile is False


def test_stasser_1992_arithmetic() -> None:
    for scenario in PAPER_SCENARIOS:
        if scenario.id not in {"stasser-1992-solve", "stasser-1992-judge"}:
            continue
        result = truth.analysis(scenario)
        assert [lean.verdict for lean in result.agent_leans] == ["billy"] * 3
        assert result.shared_only_verdict == "billy"
        assert result.pooled_verdict == "eddie"
        assert result.is_hidden_profile is True


def test_paper_scenarios_are_in_api() -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    ids = {scenario["id"] for scenario in response.json()}
    assert {scenario.id for scenario in PAPER_SCENARIOS} <= ids

    response = client.get("/api/scenarios/stasser-1985-hidden/analysis")
    assert response.status_code == 200
    assert response.json()["pooledVerdict"] == "a"


def test_stasser_1985_validation_passes() -> None:
    scenario = next(s for s in PAPER_SCENARIOS if s.id == "stasser-1985-hidden")
    result = asyncio.run(
        validator.validate_scenario(scenario, FakeClient(), model="fake", trials=3)
    )
    assert result.passed is True
