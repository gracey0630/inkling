"""Retrieval coverage on the dev questions: python -m evals.rag.run

Dev only: test.jsonl is held out. Hit@5 needs references/, which don't exist yet, so this reports
how much each category retrieves, not whether the results are correct.
"""

import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from rag.corpus import load_chunks
from rag.retriever import score_chunks

DEV = Path(__file__).parent / "questions" / "dev.jsonl"


def main() -> dict:
    chunks = load_chunks()
    questions = [json.loads(line) for line in DEV.read_text().splitlines() if line.strip()]
    top_scores = defaultdict(list)
    for q in questions:
        if q["mode"] == "summary":
            continue
        query = " ".join(filter(None, [q["question"], q["context"]]))
        scored = score_chunks(query, chunks)
        top_scores[q["category"]].append(scored[0][0] if scored else 0.0)
    return {
        "docs": len({c.doc_id for c in chunks}),
        "chunks": len(chunks),
        "questions": sum(len(s) for s in top_scores.values()),
        "median_top_score_by_category": {
            category: round(median(scores), 2) for category, scores in sorted(top_scores.items())
        },
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
