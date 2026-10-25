"""Agent layer stub: wires the signals and rag stubs into an AgentResponse.

Two modes (see docs/decisions.md): "education" answers from the trusted corpus with
citations; "summary" talks about the user's own data. Routing between them is TBD,
so the caller picks the mode for now.
"""

from typing import Literal

from contracts import AgentResponse, DataChip
from rag.stub import retrieve
from signals.stub import estimate_phase


def respond(
    question: str,
    user_id: str = "synthetic-maya",
    mode: Literal["education", "summary"] = "education",
) -> AgentResponse:
    est = estimate_phase(user_id)
    evidence = retrieve(question, {"phase": est.phase}) if mode == "education" else []
    window = est.ovulation_window
    return AgentResponse(
        mode=mode,
        text=f"STUB {mode} answer to: {question!r}",
        evidence_chips=evidence,
        data_chips=[
            DataChip(
                label="Estimated phase",
                value=f"{est.phase} (day {est.cycle_day})",
                chart_ref=est.chart_ref,
                source=est.source,
            )
        ],
        uncertainty_note=(
            f"Ovulation window {window.start} to {window.end}, confidence {est.confidence:.2f}."
            if window
            else "Not enough data yet to estimate ovulation."
        ),
        safety="none",
    )
