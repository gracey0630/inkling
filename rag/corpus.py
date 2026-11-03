"""Trusted corpus: fetch the v0 pages in manifest.csv, extract their text, split it into chunks.

Run from the repo root: python -m rag.corpus
Fetched pages go to data/raw/corpus/ (gitignored). Only documents in the manifest are indexed
(D26), and links found on pages are never followed.
"""

import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("manifest.csv")
CORPUS_DIR = REPO_ROOT / "data" / "raw" / "corpus"

# Name the project and link it, as polite crawlers do. CDC rejects the bare name with a 403.
USER_AGENT = "InklingCourseProject/0.1 (+https://github.com/gracey0630/inkling)"
REQUEST_DELAY_S = 2
MIN_WORDS = 50

# Page furniture outside <main>. Inside <main>, header and aside can hold headings and care advice.
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "form"}
SKIP_OUTSIDE_MAIN = SKIP_TAGS | {"header", "footer", "aside"}
REFERENCE_HEADINGS = {"sources", "references", "citations"}
FERTILITY_TIMING = re.compile(
    r"fertile (days|window)|safe days|ovulation calculator|best (day|time) to (try|conceive)", re.I
)
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "br", "div", "section"}
MAX_WORDS = 180
OVERLAP_WORDS = 30


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    source_org: str
    title: str
    url: str
    text: str


class _Text(HTMLParser):
    """Collect visible text as blocks, keeping only <main> when the page has one."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.all_blocks: list[str] = []
        self.main_blocks: list[str] = []
        self._buf: list[str] = []
        self._skip_tag = ""
        self._skip_depth = 0
        self._main = 0
        self._in_title = False

    def _flush(self):
        text = " ".join("".join(self._buf).split())
        self._buf = []
        if text:
            self.all_blocks.append(text)
            if self._main:
                self.main_blocks.append(text)

    def handle_starttag(self, tag, attrs):
        if self._skip_tag:
            self._skip_depth += tag == self._skip_tag
        elif tag == "br":
            self._flush()
        elif tag in SKIP_OUTSIDE_MAIN and (tag in SKIP_TAGS or not self._main):
            self._skip_tag, self._skip_depth = tag, 1
        elif tag == "title":
            self._in_title = True
        elif tag == "main":
            self._flush()
            self._main += 1
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if self._skip_tag:
            self._skip_depth -= tag == self._skip_tag
            if not self._skip_depth:
                self._skip_tag = ""
        elif tag == "title":
            self._in_title = False
        elif tag == "main":
            self._flush()
            self._main = max(0, self._main - 1)
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip_tag:
            self._buf.append(data)


def extract(html: str) -> tuple[str, str]:
    """Return (title, text) with one block per line."""
    parser = _Text()
    parser.feed(html)
    parser.close()
    parser._flush()
    blocks = parser.main_blocks or parser.all_blocks
    for i, block in enumerate(blocks):
        if block.lower().rstrip(":") in REFERENCE_HEADINGS:
            blocks = blocks[:i]
            break
    return " ".join(parser.title.split()), "\n".join(blocks)


def chunk_text(text: str) -> list[str]:
    """Group blocks into chunks of up to MAX_WORDS, overlapping when a chunk is cut."""
    chunks: list[str] = []
    words: list[str] = []
    for block in text.splitlines():
        block_words = block.split()
        if words and len(words) + len(block_words) > MAX_WORDS:
            chunks.append(" ".join(words))
            words = words[-OVERLAP_WORDS:]
        words += block_words
        while len(words) > MAX_WORDS:
            chunks.append(" ".join(words[:MAX_WORDS]))
            words = words[MAX_WORDS - OVERLAP_WORDS :]
    if words:
        chunks.append(" ".join(words))
    return chunks


def manifest(path: Path = MANIFEST) -> list[dict]:
    """The v0 documents."""
    with path.open(encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f) if row["v0"] == "yes"]


def robots_allow(url: str, cache: dict[str, RobotFileParser]) -> bool:
    """Unreadable robots.txt counts as not allowed, so we only fetch what we confirmed."""
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    if host not in cache:
        rules = RobotFileParser()
        response = requests.get(
            f"{host}/robots.txt", timeout=30, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
        rules.parse(response.text.splitlines())
        cache[host] = rules
    return cache[host].can_fetch(USER_AGENT, url)


def fetch_all(corpus_dir: Path = CORPUS_DIR) -> dict[str, str]:
    """Fetch every v0 page and return {doc_id: "ok" or why not}. A failure keeps the old copy."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    status = {}
    robots: dict[str, RobotFileParser] = {}
    for row in manifest():
        doc_id = row["doc_id"]
        if row["doc_type"] != "page":
            status[doc_id] = f"not fetched: {row['doc_type']} needs its own path (sources.md)"
            continue
        try:
            if not robots_allow(row["url"], robots):
                status[doc_id] = "blocked by robots.txt"
                continue
            time.sleep(REQUEST_DELAY_S)
            response = requests.get(row["url"], timeout=30, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
        except requests.RequestException as err:
            status[doc_id] = type(err).__name__
            print(f"FAILED {doc_id}: {err}", file=sys.stderr)
            continue
        title, text = extract(response.text)
        if len(text.split()) < MIN_WORDS:
            status[doc_id] = "too little text extracted"
            continue
        doc = {
            "doc_id": doc_id,
            "source_org": row["org"],
            "url": row["url"],
            "title": row["title"] or title,
            "text": text,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        path = corpus_dir / f"{doc_id}.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        status[doc_id] = "ok"
    return status


def load_chunks(corpus_dir: Path = CORPUS_DIR) -> list[Chunk]:
    chunks = []
    for row in manifest():
        path = corpus_dir / f"{row['doc_id']}.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for i, text in enumerate(chunk_text(doc["text"])):
            chunks.append(
                Chunk(
                    doc_id=doc["doc_id"],
                    chunk_id=f"{doc['doc_id']}#{i}",
                    source_org=doc["source_org"],
                    title=doc["title"],
                    url=doc["url"],
                    text=text,
                )
            )
    return chunks


def fertility_flags(chunks: list[Chunk]) -> list[str]:
    """Chunk ids for a person to review before indexing (sources.md)."""
    return [c.chunk_id for c in chunks if FERTILITY_TIMING.search(c.text)]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


if __name__ == "__main__":
    results = fetch_all()
    flagged = fertility_flags(load_chunks())
    print(json.dumps({"status": results, "review_fertility_timing": flagged}, indent=2))
