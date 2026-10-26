Everything in `data/` is gitignored except this file and `data/synthetic/`.

- `data/raw/`: local only.
  - `data/raw/mcphases/`: your own mcPHASES download (PhysioNet terms forbid redistribution).
    Claude is denied this folder; see CLAUDE.md.
  - `data/raw/fitbit/`: real Fitbit pulls (label `source: real`).
- `data/synthetic/`: generated data that is safe to commit. Label it `source: synthetic`.
