import pytest
from pydantic import ValidationError

from contracts import AgentResponse, DailyRecord, Evidence, PhaseEstimate, load_fixture


def test_fixtures_validate():
    for r in load_fixture("daily_records"):
        DailyRecord.model_validate(r)
    PhaseEstimate.model_validate(load_fixture("phase_estimate"))
    for e in load_fixture("evidence"):
        Evidence.model_validate(e)
    AgentResponse.model_validate(load_fixture("agent_response"))


def test_fixtures_are_synthetic():
    assert all(r["source"] == "synthetic" for r in load_fixture("daily_records"))
    assert load_fixture("phase_estimate")["source"] == "synthetic"


def test_red_flag_requires_escalation():
    bad = {**load_fixture("agent_response"), "safety": "red_flag", "escalation": None}
    with pytest.raises(ValidationError):
        AgentResponse.model_validate(bad)


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        PhaseEstimate.model_validate({**load_fixture("phase_estimate"), "surprise": 1})
