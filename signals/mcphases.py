"""mcPHASES loader, shared by the EDA, the phase model and its evals.

The data is under PhysioNet's restricted-access DUA (D18): each person uses their own download in
MCPHASES_DIR (default data/raw/mcphases/). Code that reads it must only print or return aggregates.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    load_dotenv(REPO_ROOT / ".env")
    path = Path(os.environ.get("MCPHASES_DIR", "data/raw/mcphases"))
    return path if path.is_absolute() else REPO_ROOT / path


def load(name: str, columns: list[str] | None = None, root: Path | None = None) -> pd.DataFrame:
    """One table, optionally only `columns` (those absent from the file are skipped)."""
    path = (root or data_dir()) / f"{name}.csv"
    header = pd.read_csv(path, nrows=0).columns
    usecols = None if columns is None else [c for c in columns if c in header]
    return pd.read_csv(path, usecols=usecols, low_memory=False)
