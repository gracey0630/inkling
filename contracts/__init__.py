import json
from pathlib import Path

from contracts.models import (
    SCHEMA_VERSION,
    AgentResponse,
    CheckIn,
    DailyRecord,
    DataChip,
    Escalation,
    Evidence,
    OvulationWindow,
    PhaseEstimate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    """Raw JSON from contracts/fixtures/<name>.json."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


__all__ = [
    "SCHEMA_VERSION",
    "AgentResponse",
    "CheckIn",
    "DailyRecord",
    "DataChip",
    "Escalation",
    "Evidence",
    "OvulationWindow",
    "PhaseEstimate",
    "load_fixture",
]
