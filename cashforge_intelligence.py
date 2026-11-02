"""CashForge's evidence analysis pipeline.

A lightweight, local-first implementation. It uses transparent lexical features
and explicit evidence boundaries; it does not claim transformer-level semantics.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "are", "was", "were", "you", "your", "they", "them", "their", "our",
    "but", "not", "can", "could", "would", "should", "about", "into",
    "when", "what", "why", "how", "who", "where", "which", "there",
    "then", "than", "also", "just", "very", "more", "some", "any",
}
PAIN_TERMS = {
    "annoying", "broken", "bug", "bugs", "confusing", "costly", "difficult",
    "expensive", "frustrating", "hard", "issue", "issues", "manual", "missing",
    "pain", "problem", "problems", "slow", "tedious", "waste", "workaround",
}
PAYMENT_TERMS = {
    "buy", "charge", "cost", "expensive", "paid", "pay", "paying", "payment",
    "price", "pricing", "subscription", "worth",
}
POSITIVE_TERMS = {
    "amazing", "best", "easy", "excellent", "great", "helpful", "love",
    "recommend", "solved", "useful", "works", "working",
}
NEGATION_TERMS = {"not", "never", "no", "isn't", "wasn't", "without", "hardly"}


def tokens(text: str) -> list[str]:
    return [
        word for word in re.findall(r"[a-z0-9]{2,}", str(text or "").lower())
        if word not in STOPWORDS
    ]


def _vector(text: str) -> Counter[str]:
    return Counter(tokens(text))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[k] * right[k] for k in common)
    a = math.sqrt(sum(v * v for v in left.values()))
    b = math.sqrt(sum(v * v for v in right.values()))
    return dot / (a * b) if a and b else 0.0


def _similarity(left: str, right: str) -> float:
    a, b = _vector(left), _vector(right)
    if not a or not b:
        return 0.0
    overlap = len(set(a) & set(b)) / max(1, len(set(a) | set(b)))
    return max(_cosine(a, b) * 0.78, overlap)


def _evidence_text(item: dict[str, Any]) -> str:
    return " ".join((str(item.get("title") or ""), str(item.get("excerpt") or "")))


def group_evidence(items: list[dict[str, Any]], threshold: float = 0.30) -> list[dict[str, Any]]:
    """Group related evidence without discarding any original source record."""
    groups: list[list[dict[str, Any]]] = []
    for item in sorted(items, key=lambda x: int(x.get("engagement") or 0), reverse=True):
        text = _evidence_text(item)
        best, best_score = None, 0.0
        for group in groups:
            score = _similarity(text, _evidence_text(group[0]))
            if score > best_score:
                best, best_score = group, score
        if best is not None and best_score >= threshold:
            best.append(item)
        else:
            groups.append([item])
    result = []
    for group in groups:
        representative = group[0]
        result.append({
            "label": str(representative.get("title") or "Unlabelled theme")[:120],
            "size": len(group),
            "sources": sorted({str(x.get("source") or "Unknown") for x in group}),
            "domains": sorted({
                re.sub(r"^www\\.", "", str(x.get("domain") or ""))
                for x in group if x.get("domain")
            }),
            "evidence": group,
        })
    return sorted(result, key=lambda x: x["size"], reverse=True)


def _term_hits(texts: list[str], vocabulary: set[str]) -> int:
    return sum(1 for text in texts if set(tokens(text)) & vocabulary)


def _counter_signals(texts: list[str]) -> list[str]:
    found = []
    for text in texts:
        words = tokens(text)
        if set(words) & POSITIVE_TERMS and (set(words) & PAIN_TERMS or set(words) & NEGATION_TERMS):
            found.append(text[:260])
        elif set(words) & {"solved", "fixed", "resolved", "no", "never"}:
            found.append(text[:260])
    return found[:5]


def _score_cluster(group: dict[str, Any], total: int) -> dict[str, Any]:
    evidence = group["evidence"]
    texts = [_evidence_text(x) for x in evidence]
    size = len(evidence)
    independent_sources = len(group["sources"])
    domains = len(group["domains"])
    frequency = min(25.0, round((size / max(1, total)) * 100, 1))
    pain_hits = _term_hits(texts, PAIN_TERMS)
    pain = min(25.0, round((pain_hits / max(1, size)) * 25, 1))
    payment_hits = _term_hits(texts, PAYMENT_TERMS)
    monetization = min(25.0, round((payment_hits / max(1, size)) * 25, 1))
    coverage = min(25.0, round((independent_sources * 5) + (domains * 2), 1))
    score = round(frequency + pain + monetization + coverage)
    confidence = min(100, round((min(size, 8) * 7) + (independent_sources * 9) + (domains * 4)))
    counter = _counter_signals(texts)
    return {
        "frequency": frequency,
        "problem_evidence": pain,
        "monetization_language": monetization,
        "source_coverage": coverage,
        "score": min(100, score),
        "confidence": confidence,
        "counter_signals": counter,
        "pain_mentions": pain_hits,
        "payment_mentions": payment_hits,
        "competitor_coverage": "not_assessed",
    }


def run_analysis(topic: str, objective: str, signals: list[dict[str, Any]],
                 raw_records: int, source_errors: list[str] | None = None) -> dict[str, Any]:
    """Run CashForge's specialist analysis stages over collected evidence."""
    source_errors = source_errors or []
    evidence = []
    for row in signals:
        evidence.append({
            "source": row.get("source", "Unknown"),
            "title": row.get("title", ""),
            "excerpt": row.get("excerpt", ""),
            "url": row.get("url", ""),
            "engagement": int(row.get("engagement") or 0),
            "domain": re.sub(r"^www\\.", "", str(row.get("url", "")).split("/")[2].lower())
                if "://" in str(row.get("url", "")) else "",
        })
        try:
            examples = row.get("match_examples") or "[]"
            import json
            if isinstance(examples, str):
                examples = json.loads(examples)
            for extra in examples if isinstance(examples, list) else []:
                evidence.append({
                    "source": extra.get("source", "Unknown"),
                    "title": extra.get("title", ""),
                    "excerpt": extra.get("excerpt", ""),
                    "url": extra.get("url", ""),
                    "engagement": 0,
                    "domain": re.sub(r"^www\\.", "", str(extra.get("url", "")).split("/")[2].lower())
                        if "://" in str(extra.get("url", "")) else "",
                })
        except (ValueError, TypeError, AttributeError):
            pass

    groups = group_evidence(evidence)
    findings = []
    for index, group in enumerate(groups, 1):
        score = _score_cluster(group, max(1, len(evidence)))
        gap_gate = group["size"] >= 3 and score["problem_evidence"] >= 8
        findings.append({
            "id": f"finding-{index}",
            "title": group["label"],
            "evidence_count": group["size"],
            "sources": group["sources"],
            "source_domains": group["domains"],
            "score": score,
            "potential_gap": bool(gap_gate),
            "gap_status": "candidate_needs_competitor_research" if gap_gate else "insufficient_evidence",
            "evidence": [
                {"source": x["source"], "title": x["title"], "url": x["url"],
                 "excerpt": str(x["excerpt"])[:320]}
                for x in group["evidence"][:12]
            ],
        })

    findings.sort(key=lambda x: (x["potential_gap"], x["score"]["score"]), reverse=True)
    all_text = [_evidence_text(x) for x in evidence]
    pain_count = _term_hits(all_text, PAIN_TERMS)
    payment_count = _term_hits(all_text, PAYMENT_TERMS)
    counter_count = sum(len(x["score"]["counter_signals"]) for x in findings)
    independent_sources = len({x["source"] for x in evidence})
    confidence = min(100, round((min(len(evidence), 10) * 5) + independent_sources * 10))
    stages = [
        {"id": "intake", "status": "complete", "detail": "Research objective and topic captured."},
        {"id": "evidence_review", "status": "complete", "detail": f"{len(evidence)} retained evidence records reviewed."},
        {"id": "theme_discovery", "status": "complete", "detail": f"{len(groups)} evidence themes formed."},
        {"id": "voice_of_customer", "status": "complete", "detail": f"{pain_count} records contain pain/problem language."},
        {"id": "monetization_signals", "status": "complete", "detail": f"{payment_count} records contain payment/pricing language."},
        {"id": "counterevidence_review", "status": "complete", "detail": f"{counter_count} possible counter-signals flagged for human review."},
        {"id": "competitor_analysis", "status": "not_run", "detail": "Competitor evidence has not yet been collected; no market-gap claim is confirmed."},
        {"id": "skeptic_review", "status": "complete", "detail": "Unsupported demand, competition and revenue claims are withheld."},
    ]
    if source_errors:
        stages.insert(1, {"id": "source_health", "status": "partial", "detail": "; ".join(source_errors)[:700]})
    return {
        "schema_version": "cashforge-analysis-v1",
        "topic": topic,
        "objective": objective,
        "pipeline": stages,
        "evidence": {
            "raw_records": raw_records,
            "retained_records": len(evidence),
            "independent_sources": independent_sources,
            "problem_language_records": pain_count,
            "payment_language_records": payment_count,
            "counter_signal_count": counter_count,
            "confidence": confidence,
        },
        "opportunities": findings[:20],
        "decision": {
            "status": "candidate_opportunities" if any(x["potential_gap"] for x in findings) else "more_evidence_needed",
            "summary": (
                "Potential problem clusters were found, but competitor coverage and willingness to pay still require validation."
                if any(x["potential_gap"] for x in findings)
                else "The current evidence is not strong enough to call a market gap. Collect more independent evidence or narrow the research question."
            ),
        },
        "limitations": [
            "Similarity is a lightweight local text-feature method, not a neural semantic embedding.",
            "Public discussion frequency does not prove market demand or willingness to pay.",
            "Competitor coverage is not assessed in this run.",
            "Priority scores are directional research aids, not revenue forecasts.",
        ],
    }
