# Decisions

Newest at the bottom. One entry per decision. To change a decided item, add a new entry and point to the old one.

---

### D1. Three layers plus app, organized by architecture
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:** `signals/`, `rag/`, `agent/` and `app/`, each self-contained. Anyone can work on any layer.
- **Why:** The layers can be built in parallel, and the split matches how the system is graded and demoed.
- **Alternatives:** Organize by feature or by person (folders become stale when work shifts).

### D2. Contract-first with stubs
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:** Handoffs are Pydantic models in `contracts/` (`extra="forbid"`, versioned) with JSON fixtures. Every layer ships a stub on day one.
- **Why:** The walking skeleton works before any layer is real, and contract drift fails tests instead of the demo.
- **Alternatives:** Shared docs only (drift); JSON Schema files (more tooling).

### D3. Contract v0.1 refinements over the timeline draft
- **Date:** 2026-10-24 · **Status:** proposed, flexible. Expected to change as data access becomes clear (Google Health API fields, mcPHASES schema, check-in fields from D5).
- **Decision:**
  - Wearable fields are optional (None = missing), and units appear in field names.
  - Add `user_id`, `schema_version` and `CheckIn.bc_taken`.
  - `range_days` becomes `ovulation_window{start,end}`. Phase gets `"unknown"`, plus `method` and `source`.
  - `Evidence` gets `doc_id`/`chunk_id`.
  - `AgentResponse` gets `mode`, a required `uncertainty_note`, an optional `escalation` (required on red_flag), `fallback_used`, and structured `DataChip`s.
- **Why:** Missing data must be representable, the citation eval needs chunk ids, and "± days" was ambiguous.
- **Alternatives:** Keep the timeline shapes verbatim.

### D4. The uncertainty range is a feature
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:** Every estimate carries a window and a confidence. When signal is weak, show it wide or say "not enough data yet".
- **Why:** Fitbit signals may be too noisy for a point estimate, and the course rewards honest uncertainty.
- **Alternatives:** Point estimate only.

### D5. Red-flag detection and routing
- **Date:** 2026-10-24 · **Status:** open (needs more team discussion)
- **Why it matters:**
  - Missing a real red flag is the worst failure this app can have.
  - Unsafe outputs and diagnosis language are named red flags in the grading.
  - The approach decides what the check-in must collect, so it affects the contracts.
- **Starting point (from the timeline):** rules first, LLM second, plus a banned-phrases check on outputs ("you have…", "you are ovulating").
- **Approaches to weigh:**
  - Rules on structured check-in fields (exact and testable, but needs fields like "soaking hourly?").
  - The LLM extracts facts from chat and coded rules decide (handles paraphrase and negation; the decision stays traceable).
  - Keyword matching (simple, but brittle; best kept as a safety net when the LLM is down).
- **Also open:** the rule list itself (draft it from ACOG/MedlinePlus with citations), what "caution" vs "red_flag" means, and whether the LLM can ever lower a rule hit (proposal: never).
- **Deadlines:** decide the check-in fields before the Oct 28 contract lock if possible. The router is built Nov 16–19.

### D6. Graceful fallback on every external dependency
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:** If the Fitbit API fails, use cached data. If the LLM fails, use canned cited answers. If wearable signal is missing, use the calendar-count estimator. Each fallback is visible to the user (`fallback_used`).
- **Why:** A happy-path-only demo is a named red flag.

### D7. Agent has two modes: education and summary
- **Date:** 2026-10-24 · **Status:** decided; routing method open
- **Decision:**
  - **Education** answers general questions from the trusted corpus, with citations.
  - **Summary** is a conversational agent over the user's own data: weekly synthesis and "what's going on with me".
  - Both share safety checks and return `AgentResponse`.
- **Why:** Personal-data synthesis and general education need different grounding and different prompts.
- **Open:**
  - How a question is routed (user toggle, classifier, or LLM tool choice). The stub uses a toggle.
  - Whether to build a clinician summary. This would be a one-page handout to bring to an appointment: period dates and cycle lengths, symptom and check-in trends, wearable patterns, BC use, any flags raised, and suggested questions. It would be generated from the data (not free LLM text) and labeled real or synthetic with a "not a diagnosis" note. It would be offered on escalation (`Escalation.summary_pdf`) and on request.
  - Options: a downloadable PDF, an on-screen/copyable summary only, or cut.

### D8. LLM provider: OpenAI, a personal key per person
- **Date:** 2026-10-24 · **Status:** decided (model name open)
- **Why:** Everyone already has access.

### D9. App framework: Streamlit
- **Date:** 2026-10-24 · **Status:** decided
- **Why:** The whole team writes Python, it's fast to build, and it has a built-in test harness (`AppTest`).
- **Alternatives:** Gradio; FastAPI + web frontend (more flexible Cycle Clock, more work).

### D10. Environment: venv + requirements.txt
- **Date:** 2026-10-24 · **Status:** decided
- **Why:** It needs no extra tools, so anyone can clone and run.
- **Alternatives:** uv, conda, poetry.

### D11. mcPHASES stays local and never reaches an LLM
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:** Only credentialed people handle the raw data. It stays on their machine in `data/raw/`, and only aggregate metrics are shared.
- **Why:** PhysioNet credentialed-access terms.

### D12. Embeddings + vector store
- **Date:** 2026-10-24 · **Status:** open
- **Notes:** The corpus is small (30 to 50 docs). A local option also works offline at the demo.

### D13. Storage for check-ins and cached data
- **Date:** 2026-10-24 · **Status:** open
- **Options:** SQLite; JSON files.

### D14. What user data is sent to the LLM
- **Date:** 2026-10-24 · **Status:** open
- **Proposal:** Send derived features and summaries, not raw Fitbit JSON, and only after the user opts in.

### D15. Phase model approach
- **Date:** 2026-10-24 · **Status:** open
- **Options:** Rules (temperature shift / RHR rise over baseline), or ML trained on mcPHASES. Either way, the calendar count is the fallback.

### D16. v1 scope cuts from the whiteboard
- **Date:** 2026-10-24 · **Status:** open
- **Candidates for stretch/out of scope:** sleep-stage model, activity suggestions, young-adult slider triggers, guideline→action-plan matching, FHIR export (PDF only).

### D17. Gate date changes
- **Date:** 2026-10-24 · **Status:** decided
- **Decision:**
  - Integration #1 moves from Fri Nov 20 to **Thu Nov 19**.
  - The Week 13 integration checkpoint and mock demo is **Fri Dec 4**.
- **Why:** Nov 20 is the Quiz 2 class day. Dec 4 is confirmed on the course site, and that class includes teams red-teaming each other's agents, so our safety red-team set doubles as prep.
