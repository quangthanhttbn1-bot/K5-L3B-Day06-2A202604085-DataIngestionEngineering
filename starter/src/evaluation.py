"""Evidence-based retrieval scoring and trace summaries."""
from collections import defaultdict
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    quotes = question.get("evidence_quotes") or [question.get("evidence_quote", "")]
    quotes = [" ".join(q.casefold().split()) for q in quotes if q and q.strip()]
    valid_sources = set(question.get("gold_source_ids", [question.get("gold_source_id")]))
    valid_pages = set(question.get("gold_pages", [question.get("gold_page")]))
    def is_evidence_hit(hit: dict[str, Any]) -> bool:
        source_ok = hit.get("document_id") in valid_sources or hit.get("source") in valid_sources
        page_ok = (hit.get("page") in valid_pages or
                   hit.get("metadata", {}).get("unit_id") in valid_pages)
        text = " ".join(hit.get("text", "").casefold().split())
        quote_ok = any(q in text for q in quotes) if quotes else False
        return source_ok and page_ok and quote_ok
    flags = [is_evidence_hit(hit) for hit in hits]
    return {"id": question["id"], "split": question["split"],
            "question": question["question"], "hits": hits,
            "hit_at_1": bool(flags and flags[0]),
            "evidence_hit_at_3": any(flags[:3]),
            "gold_source_id": question.get("gold_source_id"),
            "gold_page": question.get("gold_page"),
            "evidence_quotes": question.get("evidence_quotes", [question.get("evidence_quote")]),
            "filter": question.get("filter")}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        groups[trace["split"]].append(trace)
    result = {}
    for split, rows in groups.items():
        n = len(rows)
        result[split] = {"n": n, "hit_at_1": sum(r["hit_at_1"] for r in rows),
                         "evidence_hit_at_3": sum(r["evidence_hit_at_3"] for r in rows),
                         "hit_at_1_rate": sum(r["hit_at_1"] for r in rows) / n,
                         "evidence_hit_at_3_rate": sum(r["evidence_hit_at_3"] for r in rows) / n}
    return result
