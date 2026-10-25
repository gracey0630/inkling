from contracts import DailyRecord, PhaseEstimate
from signals.stub import estimate_phase, get_daily_records


def test_stub_matches_contract():
    records = get_daily_records("u1")
    assert records and all(isinstance(r, DailyRecord) and r.user_id == "u1" for r in records)
    assert isinstance(estimate_phase("u1"), PhaseEstimate)
