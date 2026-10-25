"""Signals layer stub: contract-shaped fake data until the real pipeline lands."""

from contracts import DailyRecord, PhaseEstimate, load_fixture


def get_daily_records(user_id: str) -> list[DailyRecord]:
    return [
        DailyRecord.model_validate({**r, "user_id": user_id}) for r in load_fixture("daily_records")
    ]


def estimate_phase(user_id: str) -> PhaseEstimate:
    return PhaseEstimate.model_validate({**load_fixture("phase_estimate"), "user_id": user_id})
