# Inkling: working rules

Inkling is a personal health assistant that helps young women understand their menstrual
cycle using Fitbit data and trusted sources. It is a course project and **not a medical device**.

## Safety stance (non-negotiable)
- Never use diagnosis language ("you have PCOS", "you are ovulating", "you are pregnant").
  Describe patterns ("your temperature has been higher than your usual") and add
  "worth asking a clinician" where it fits.
- Always show uncertainty: an estimate comes with its window/confidence, or says "not enough data yet".
- Red flags (e.g. soaking a pad hourly, severe pain, 90+ days without a period) pause the
  conversation and route to care. Rules decide first; the LLM never overrides a rule.
- Education answers cite the trusted corpus. If nothing relevant is retrieved, say "I don't know".

## Architecture
- `docs/architecture.md` is a **draft for discussion**. Don't treat it as settled. If a task depends on an open
  decision or would change the architecture, stop and propose it to the team first rather than implementing.
- Layers: `signals/`, `rag/`, `agent/`, `app/`. They talk only through the models in `contracts/models.py`.
- Work on whichever layer your task touches. Keep changes to a layer's internals inside that layer.
- **Changing a contract:** update `contracts/models.py`, the matching `contracts/fixtures/*.json`,
  bump `SCHEMA_VERSION`, and add an entry to `docs/decisions.md`, all in the same PR.
- Each layer keeps a `stub.py` with the contract's signature. Real code replaces it behind the same interface.
- Update the stubbed-vs-real table in `docs/architecture.md` when something becomes real.

## Data rules
- Every data view and output is labeled `real` or `synthetic` (the `source` fields in the contracts).
- Never commit mcPHASES/PhysioNet data (the terms forbid redistribution), secrets, or real personal
  health data. Only synthetic fixtures are committable. Raw data goes in `data/raw/` (gitignored).
- Never send mcPHASES rows to an LLM API. Eval scripts print aggregate metrics only.

## Definition of done
Merged to main, runs from a clean clone, has at least one test or eval, and the UI labels its data source.

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                        # all tests
ruff check . && ruff format .                 # lint + format
python -m streamlit run app/streamlit_app.py  # run the app (from repo root)
```

Evals: each layer's eval is `evals/<layer>/run.py`, run as `python -m evals.<layer>.run`. It prints a
JSON dict of metrics (aggregate only, never data rows).

## Style
- Python 3.11+, type hints on public functions, ruff (config in `pyproject.toml`).
- Tests live in `tests/test_<layer>.py`.
- Prefer simple code. Plain functions over classes; no framework unless the team has agreed to it.
- Ask before adding a dependency or framework, and log the choice in `docs/decisions.md`.
- Don't pick the LLM model, embeddings, or vector store on your own: check `docs/decisions.md` for what's open.
