from agent.stub import respond
from contracts import AgentResponse


def test_stub_matches_contract():
    for mode in ("education", "summary"):
        r = respond("why am I tired?", mode=mode)
        assert isinstance(r, AgentResponse) and r.mode == mode
        assert r.uncertainty_note
    assert respond("why am I tired?").evidence_chips  # education answers cite sources
