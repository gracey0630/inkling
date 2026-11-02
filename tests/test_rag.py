import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from contracts import Evidence
from rag.corpus import (
    MAX_WORDS,
    Chunk,
    chunk_text,
    extract,
    fertility_flags,
    load_chunks,
    manifest,
)
from rag.retriever import best_window, score_chunks, terms, to_evidence
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


def make_chunk(i: int, text: str) -> Chunk:
    return Chunk(f"doc{i}", f"doc{i}#0", "NHS", "Title", "https://www.nhs.uk/x", text)


def test_extract_keeps_main_and_drops_page_furniture():
    html = """<html><head><title> Periods </title><style>.a{}</style></head><body>
    <svg><title>Logo</title></svg><nav>Menu</nav>
    <main><h1>Periods</h1><p>A cycle lasts<br>about 28 days.</p>
    <script>track()</script></main><footer>Cookies</footer></body></html>"""
    title, text = extract(html)
    assert title == "Periods"
    assert text.splitlines() == ["Periods", "A cycle lasts", "about 28 days."]


def test_chunks_respect_the_size_limit_and_keep_every_word():
    words = [f"w{i}" for i in range(500)]
    chunks = chunk_text("\n".join([" ".join(words[:50]), " ".join(words[50:])]))
    assert len(chunks) > 1
    assert all(len(c.split()) <= MAX_WORDS for c in chunks)
    assert set(" ".join(chunks).split()) == set(words)


def test_retrieval_ranks_the_matching_chunk_first():
    chunks = [
        make_chunk(0, "heavy periods can mean soaking a pad every hour"),
        make_chunk(1, "the pill is a birth control method"),
    ]
    assert score_chunks("how heavy is too heavy for periods", chunks)[0][1].doc_id == "doc0"


def test_retrieval_returns_nothing_without_a_match():
    assert score_chunks("best pizza nearby", [make_chunk(0, "heavy periods")]) == []


def test_evidence_matches_contract_with_verbatim_snippet():
    chunk = make_chunk(0, "heavy periods can mean soaking a pad every hour")
    evidence = to_evidence(chunk, "heavy", datetime(2026, 11, 1, tzinfo=UTC))
    assert isinstance(evidence, Evidence)
    assert evidence.snippet in chunk.text


def test_extract_recovers_from_unclosed_tags_in_skipped_regions():
    html = "<nav><ul><li>Home<li>About<source></ul></nav><main><p>Care advice.</p></main>"
    assert extract(html)[1] == "Care advice."


def test_extract_keeps_callouts_inside_main_and_drops_reference_lists():
    html = """<header>Site</header><main><aside><p>Call a doctor.</p></aside><p>Body.</p>
    <h2>Sources</h2><p>Smith 2020.</p></main>"""
    assert extract(html)[1].splitlines() == ["Call a doctor.", "Body."]


def test_snippet_shows_the_matching_passage():
    text = " ".join(["filler"] * 150 + ["soaking", "a", "pad"])
    assert "soaking" in best_window(text, {"soaking"})


def test_terms_fold_plurals_and_expand_abbreviations():
    assert terms("side effects of bc") == ["side", "effect", "birth", "control"]


def test_only_manifest_documents_are_indexed(tmp_path):
    doc_id = manifest()[0]["doc_id"]
    for name in (doc_id, "not-on-the-whitelist"):
        doc = {"doc_id": name, "source_org": "X", "title": "T", "url": "u", "text": "words"}
        (tmp_path / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    assert {c.doc_id for c in load_chunks(tmp_path)} == {doc_id}


def test_fertility_timing_chunks_are_flagged():
    assert fertility_flags([make_chunk(0, "Track your fertile days here")]) == ["doc0#0"]


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


MANIFEST = Path(__file__).resolve().parents[1] / "rag" / "manifest.csv"


def test_manifest_is_valid():
    rows = list(csv.DictReader(MANIFEST.open()))
    assert rows and len({r["doc_id"] for r in rows}) == len(rows), "duplicate doc_id"
    for r in rows:
        assert r["url"].startswith("https://"), r["doc_id"]
        assert r["doc_type"] in {"page", "research", "device_docs"}, r["doc_id"]
        assert r["license"] in {"public domain", "CC BY", "CC BY-NC", "CC BY 4.0"}, r["doc_id"]
        assert r["v0"] in {"yes", "no"}, r["doc_id"]
