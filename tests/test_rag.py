import json
from collections import Counter
from pathlib import Path

from contracts import Evidence
from rag.stub import retrieve

QUESTIONS = Path(__file__).resolve().parents[1] / "evals" / "rag" / "questions"
FIELDS = {"id", "question", "context", "mode", "category", "in_scope", "group", "added"}
MODES = {"education", "summary", "both"}
CATEGORIES = {
    "cycle_basics",
    "symptoms",
    "late_irregular",
    "bleeding_red_flags",
    "birth_control",
    "pcos",
    "wearable",
    "clinician",
    "exercise",
    "weekly_review",
    "out_of_scope",
}


def load_questions(split: str) -> list[dict]:
    lines = (QUESTIONS / f"{split}.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_stub_matches_contract():
    results = retrieve("what is the luteal phase?")
    assert results and all(isinstance(e, Evidence) for e in results)


def test_question_schema():
    for q in load_questions("dev") + load_questions("test"):
        assert set(q) == FIELDS, q["id"]
        assert q["question"].strip() and q["mode"] in MODES and q["category"] in CATEGORIES
        assert isinstance(q["in_scope"], bool)


def test_split_has_no_leaks():
    dev, test = load_questions("dev"), load_questions("test")
    ids = Counter(q["id"] for q in dev + test)
    assert all(n == 1 for n in ids.values()), "duplicate id"
    dev_groups = {q["group"] for q in dev} - {None}
    test_groups = {q["group"] for q in test} - {None}
    assert not dev_groups & test_groups, "a near-twin group spans dev and test"


def test_every_category_on_both_sides():
    dev, test = load_questions("dev"), load_questions("test")
    assert {q["category"] for q in dev} == {q["category"] for q in test} == CATEGORIES
