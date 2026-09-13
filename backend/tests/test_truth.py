from __future__ import annotations

from app import truth
from app.models import AgentPersona, Candidate, Fact, Scenario
from app.samples import SAMPLES_BY_ID
from app.scenario import DEFAULT_SCENARIO_ID


def test_bundled_scenario_hidden_profile() -> None:
    s = SAMPLES_BY_ID[DEFAULT_SCENARIO_ID]
    assert truth.shared_only_verdict(s) == "john"
    assert truth.pooled_verdict(s) == "sally"
    assert truth.is_hidden_profile(s)
    assert truth.decisive_fact_ids(s) == truth.unique_fact_ids(s)
    assert len(truth.unique_fact_ids(s)) == 14
    assert set(truth.alone_votes(s).values()) == {"john"}


def _tiny() -> Scenario:
    return Scenario(
        id="tiny",
        title="t",
        brief="b",
        candidates=[
            Candidate(id="a", name="A", blurb=""),
            Candidate(id="b", name="B", blurb=""),
            Candidate(id="c", name="C", blurb=""),
        ],
        agents=[AgentPersona(id="x", name="X", role="r", style="s")],
        facts=[
            Fact(id="f1", candidate_id="a", valence="pro", weight=3, text="t"),
            Fact(id="f2", candidate_id="b", valence="pro", weight=2, text="t"),
            Fact(id="f3", candidate_id="b", valence="con", weight=2, text="t"),
        ],
        distribution={"x": ["f1", "f2", "f3"]},
    )


def test_tiny_three_candidate_scenario() -> None:
    s = _tiny()
    assert truth.scores(s, ["f1", "f2", "f3"]) == {"a": 3, "b": 0, "c": 0}
    assert truth.pooled_verdict(s) == "a"
    assert truth.decisive_fact_ids(s) == {"f1", "f3"}
    assert not truth.is_hidden_profile(s)  # shared == pooled here


def test_tie_is_undecided() -> None:
    s = _tiny()
    assert truth.verdict(s, ["f2"]) == "b"
    assert truth.verdict(s, ["f2", "f3"]) == "undecided"
