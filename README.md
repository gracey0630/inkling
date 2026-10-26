# Inkling

A personal health assistant that helps young women understand their menstrual cycle and how
it shows up in their body. It combines wearable data (Fitbit) with cited answers from trusted
sources (ACOG, NICHD, MedlinePlus, NHS, CDC). Inkling is **not a medical device**: it describes
patterns, shows its uncertainty, and points to a clinician when something looks worth checking.

Course project for Columbia BINF 4070 / COMS 4995, *Personal Health Agent* (Fall 2026).

## Architecture

The **signals** layer turns wearable data and daily check-ins into `DailyRecord`s and a
`PhaseEstimate` with an explicit uncertainty window. The **rag** layer retrieves cited `Evidence`
from a trusted-source corpus. The **agent** layer combines the two in one of two modes: education
(cited answers) or summary (talking about your own data, including the clinician summary).
It runs every answer through safety checks and returns an `AgentResponse` to the **app**
(Streamlit). The layers talk only through the typed models in `contracts/`, and each layer
ships a stub, so the system runs end to end before any layer is real.
Details: [docs/architecture.md](docs/architecture.md).

## Quickstart

```bash
git clone https://github.com/gracey0630/inkling.git && cd inkling
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
python -m streamlit run app/streamlit_app.py
```

Copy `.env.example` to `.env` when you need API keys.

## Layers

| Folder | What it does |
|---|---|
| `contracts/` | Pydantic models for every handoff plus example JSON fixtures. Single source of truth. |
| `signals/` | Fitbit + mcPHASES ingest, baselines, phase/ovulation estimate, missing-data handling |
| `rag/` | Trusted corpus, chunking, retrieval with citations |
| `agent/` | Orchestration, education/summary modes, red-flag routing, clinician summary |
| `app/` | Streamlit UI: check-in, Cycle Clock, chat |
| `evals/` | One folder per layer; each gets a `run.py` run as `python -m evals.<layer>.run` |
| `data/` | Local only, gitignored except `data/synthetic/` |

## Docs

- [docs/timeline.md](docs/timeline.md): schedule and progress checklist (source of truth)
- [docs/architecture.md](docs/architecture.md): diagram, contracts, what is stubbed vs real
- [docs/decisions.md](docs/decisions.md): decision log
- [CLAUDE.md](CLAUDE.md): working rules (for people and for Claude Code)
