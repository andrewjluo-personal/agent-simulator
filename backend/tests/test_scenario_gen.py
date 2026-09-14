from __future__ import annotations

import pytest

from app import scenario_gen, truth
from app.samples import HIRING_PANEL_V1


def test_redistribute_preserves_hidden_profile() -> None:
    base = HIRING_PANEL_V1
    scenario = scenario_gen.redistribute(base, 7, 1)

    assert truth.is_hidden_profile(scenario)
    assert set().union(*scenario.distribution.values()) == {f.id for f in base.facts}
    shared = truth.shared_fact_ids(base)
    assert all(shared <= set(scenario.distribution[agent.id]) for agent in scenario.agents)
    assert {truth.verdict(scenario, hand) for hand in scenario.distribution.values()} == {"john"}
    assert truth.pooled_verdict(scenario) == "sally"
    assert all(
        truth.decisive_fact_ids(base) & set(scenario.distribution[agent.id])
        for agent in scenario.agents
    )
    assert scenario.id == "hiring-panel-7"


def test_redistribute_requires_one_decisive_fact_per_agent() -> None:
    base = HIRING_PANEL_V1
    with pytest.raises(ValueError, match="decisive"):
        scenario_gen.redistribute(base, len(truth.decisive_fact_ids(base)) + 1, 1)
