"""Interface contracts between layers. Single source of truth.

DRAFT (v0.1): a starting point, not final. Expect fields to change as we learn what data is
actually accessible (Google Health API fields, mcPHASES schema, check-in design).

Changing a model? Update the matching fixture in contracts/fixtures/ in the same PR,
bump SCHEMA_VERSION, and add an entry to docs/decisions.md.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1"

DataSource = Literal["real", "synthetic"]
MixedSource = Literal["real", "synthetic", "mixed"]
Bleeding = Literal["none", "spot", "light", "medium", "heavy"]
Phase = Literal["menstrual", "follicular", "ovulatory", "luteal", "unknown"]
Safety = Literal["none", "caution", "red_flag"]


class Contract(BaseModel):
    # Unknown fields are an error, so contract drift fails loudly instead of silently.
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION


# --- signals -> agent ---------------------------------------------------------


class CheckIn(Contract):
    """The 15-second self-report. Every field is optional: a skipped question is None."""

    energy: int | None = Field(None, ge=1, le=5)
    bleeding: Bleeding | None = None
    pain: int | None = Field(None, ge=0, le=10)
    symptoms: list[str] = []
    bc_taken: bool | None = None  # birth control taken today; None = not on BC or not logged


class DailyRecord(Contract):
    """One user-day. Missing wearable values are None, never 0."""

    user_id: str
    date: date
    rhr_bpm: float | None = None
    hrv_rmssd_ms: float | None = None
    skin_temp_dev_c: float | None = None  # deviation from personal baseline, degrees C
    sleep_min: int | None = None
    steps: int | None = None
    checkin: CheckIn | None = None
    source: DataSource


class OvulationWindow(Contract):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self):
        if self.end < self.start:
            raise ValueError("ovulation_window.end is before start")
        return self


class PhaseEstimate(Contract):
    """Best guess plus honest uncertainty. A wide window or phase='unknown' is a valid answer."""

    user_id: str
    as_of: date
    phase: Phase
    cycle_day: int | None = Field(None, ge=1)
    ovulation_est_date: date | None = None
    ovulation_window: OvulationWindow | None = None
    confidence: float = Field(ge=0, le=1)
    method: Literal["calendar", "wearable"]
    signals_used: list[str] = []
    source: MixedSource
    chart_ref: str | None = None  # key the app resolves to a chart, e.g. "cycle_clock"


# --- rag -> agent -------------------------------------------------------------


class Evidence(Contract):
    """One retrieved, citable chunk. Returned by rag.retrieve(query, user_context)."""

    doc_id: str
    chunk_id: str
    source_org: str  # must be on the trusted-source whitelist
    title: str
    url: str
    snippet: str
    retrieved_at: datetime


# --- agent -> app -------------------------------------------------------------


class DataChip(Contract):
    label: str
    value: str
    chart_ref: str | None = None
    source: MixedSource


class Escalation(Contract):
    reason: str
    summary_pdf: str | None = None  # path or URL to the clinician summary
    nearby_care: str | None = None


class AgentResponse(Contract):
    mode: Literal["education", "summary"]
    text: str
    evidence_chips: list[Evidence] = []
    data_chips: list[DataChip] = []
    uncertainty_note: str = Field(min_length=1)
    safety: Safety
    escalation: Escalation | None = None
    fallback_used: bool = False  # true when a cached/canned path answered instead of the live one

    @model_validator(mode="after")
    def _red_flag_escalates(self):
        if self.safety == "red_flag" and self.escalation is None:
            raise ValueError("safety='red_flag' requires an escalation")
        return self
