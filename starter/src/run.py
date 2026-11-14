"""Build corpus, ingest three strategies and emit reproducible retrieval traces."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_html, split_html_units
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
DOCUMENT_ID = "pg7213-my-life-and-work"
SOURCE = "https://www.gutenberg.org/cache/epub/7213/pg7213-images.html"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    load_dotenv(ROOT / ".env")
    RESULTS.mkdir(exist_ok=True)
    source_path = DATA / "pg7213-images.html"
    if not source_path.is_file():
        raise FileNotFoundError(f"Corpus HTML is missing: {source_path}")
    source_page = load_html(source_path, DOCUMENT_ID, SOURCE, {
        "category": "technology", "license": "Project Gutenberg License",
    })[0]
    units = split_html_units(source_page)
    short_units = [u.metadata["unit_id"] for u in units if len(u.text) < 1500]
    if len(units) < 30 or short_units:
        raise ValueError(f"Corpus needs >=30 units of >=1500 chars; got {len(units)}, short={short_units}")
    manifest = {
        "source_id": DOCUMENT_ID, "title": "My Life and Work",
        "authors": ["Henry Ford", "Samuel Crowther"], "topic": "Technology",
        "source_path_or_url": SOURCE,
        "local_snapshot": "data/pg7213-images.html",
        "license_or_permission": "Project Gutenberg License; eBook 7213. Verify applicable local terms before redistribution.",
        "accessed_at": date.today().isoformat(),
        "snapshot_sha256": __import__("hashlib").sha256(source_path.read_bytes()).hexdigest(),
        "unitization": "HTML text from Gutenberg START/END markers; ordered paragraph groups, min 1500 chars, max 5000 where paragraph boundaries permit; front matter before body marker excluded.",
        "units": [{"page_id": u.metadata["unit_id"], "section": u.metadata["section"],
                   "char_count": len(u.text), "char_start": u.metadata["char_start"],
                   "char_end": u.metadata["char_end"],
                   "content_sha256": u.metadata["content_sha256"]} for u in units],
        "unit_count": len(units), "total_chars": sum(len(u.text) for u in units),
    }
    _write_json(DATA / "manifest.json", manifest)

    questions_path = DATA / "benchmark.json"
    if not questions_path.is_file():
        raise FileNotFoundError(f"Create and evidence-check at least 20 questions first: {questions_path}")
    questions = json.loads(questions_path.read_text(encoding="utf-8-sig"))
    _validate_questions(questions, units)

    embedder = MyEmbedder()
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()
    strategies = {
        "A": [c for page in units for c in fixed_size(page, size=500, overlap=50)],
        "B": [c for page in units for c in by_paragraph(page, max_size=1200)],
        "C": [c for page in units for c in by_paragraph(page, max_size=1200)],
    }
    report = {"model": {"provider": "Sentence Transformers (local)", "name": embedder.model_name,
                         "dimensions": embedder.dimensions, "normalization": "L2",
                         "query_document_handling": "encode_query / encode_document"},
              "vector_store": "PostgreSQL + pgvector; exact cosine distance (<=>), local Compose service",
              "strategies": {}, "cost_usd": 0}
    traces = []
    vector_cache: dict[str, list[list[float]]] = {}
    for name, chunks in strategies.items():
        started = perf_counter()
        reused = store.is_current(name, chunks)
        if not reused:
            cache_key = "B" if name == "C" else name
            vectors = vector_cache.get(cache_key)
            if vectors is None:
                vectors = embedder.embed_documents([c.text for c in chunks])
                vector_cache[cache_key] = vectors
            store.upsert(name, chunks, vectors)
        elapsed = perf_counter() - started
        sizes = [len(c.text) for c in chunks]
        report["strategies"][name] = {"chunk_count": len(chunks), "total_chars": sum(sizes),
            "length_chars": {"min": min(sizes), "median": sorted(sizes)[len(sizes)//2], "max": max(sizes)},
            "ingest_seconds": round(elapsed, 3), "reused_existing": reused, "cost_usd": 0}
        for question in questions:
            query_vector = embedder.embed_query(question["question"])
            hits = store.search(name, query_vector, 3,
                                filters=question.get("filter") if name == "C" else None)
            traces.append({"strategy": name, **evaluate_query(question, hits)})
    _write_json(RESULTS / "traces.json", traces)
    report["retrieval_metrics"] = {
        name: {split: summarize([t for t in traces if t["strategy"] == name and t["split"] == split]).get(split)
               for split in ("dev", "test")} for name in strategies
    }
    _write_json(RESULTS / "run_summary.json", report)


def _validate_questions(questions: list[dict], units: list) -> None:
    required = {"id", "split", "question", "expected_answer", "gold_source_id", "gold_page", "evidence_quote"}
    for q in questions:
        missing = required - q.keys()
        if missing:
            raise ValueError(f"Question missing {sorted(missing)}: {q.get('id', '<no id>')}")
        if q["split"] not in {"dev", "test"}:
            raise ValueError(f"Invalid split in question {q['id']}")
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Question IDs must be unique")
    if len(questions) < 20:
        raise ValueError(f"Need at least 20 benchmark questions; found {len(questions)}")
    if sum(q.get("split") == "dev" for q in questions) < 15 or sum(q.get("split") == "test" for q in questions) < 5:
        raise ValueError("Benchmark needs at least 15 dev and 5 test questions")
    filtered = [q for q in questions if q.get("filter")]
    if len(filtered) < 3 or not any(q["split"] == "test" for q in filtered):
        raise ValueError("Need at least 3 metadata-filter questions, including one test question")
    by_id = {u.metadata["unit_id"]: u for u in units}
    for q in questions:
        if q.get("gold_source_id") != DOCUMENT_ID or q.get("gold_page") not in by_id:
            raise ValueError(f"Invalid gold source/page in {q.get('id')}")
        quote = " ".join(q.get("evidence_quote", "").split())
        normalized_source = " ".join(by_id[q["gold_page"]].text.split())
        if not quote or quote.casefold() not in normalized_source.casefold():
            raise ValueError(f"Evidence quote not verified in source unit for {q.get('id')}")
        if q.get("filter"):
            unit = by_id[q["gold_page"]]
            if any(str(unit.metadata.get(k)) != str(v) for k, v in q["filter"].items()):
                raise ValueError(f"Filter conflicts with source metadata in {q.get('id')}")


if __name__ == "__main__":
    main()
