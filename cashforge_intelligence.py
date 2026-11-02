"""CashForge Intelligence: explainable, local-first market research analysis.

This is an original standard-library implementation. It uses weighted lexical
retrieval and conservative clustering rather than claiming neural embeddings.
All scores are triage signals, never proof of demand or revenue.
"""
from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

STOP = set("""
a an the and or but if then else when while for to of in on at by from with
without into onto about over under is are was were be been being it its this
that these those i me my we us our you your he she they them their as not no
do does did done have has had can could would should may might will just very
more most some any each few many much such than too also
""".split())
PAIN = set("annoying broken bug bugs confusing costly difficult expensive frustrating hard issue issues manual missing pain painful problem problems slow tedious waste workaround unreliable complicated".split())
PAY = set("buy charge cost expensive paid pay paying payment price pricing subscription worth budget spend spending".split())
SOLUTION = set("alternative alternatives workaround tool app software product service solution solve solved fix fixed automate automation".split())
POSITIVE = set("amazing best easy excellent great helpful love recommend solved useful works working".split())
NEGATIVE = set("bad broken hate terrible frustrating useless disappointed failed worse".split())
SPAM = ("subscribe now", "click here", "dm me", "buy now", "limited offer", "make money fast")


def tokens(value: Any) -> list[str]:
    words = re.findall(r"[a-z0-9]{2,}", str(value or "").lower())
    return [w for w in words if w not in STOP]


def normalized_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _tfidf_vectors(texts: list[str]) -> list[dict[str, float]]:
    docs = [Counter(tokens(t)) for t in texts]
    n = max(1, len(docs))
    df = Counter(term for doc in docs for term in doc)
    vectors = []
    for doc in docs:
        vector = {}
        for term, count in doc.items():
            idf = math.log(1 + (n + 1) / (1 + df[term]))
            vector[term] = (1 + math.log(count)) * idf
        vectors.append(vector)
    return vectors


def _similarity(a: dict[str, float], b: dict[str, float]) -> float:
    return _cosine(a, b)


def _domain(url: str) -> str:
    try:
        return (urlparse(str(url)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _record_text(row: dict[str, Any]) -> str:
    return normalized_text(str(row.get("title") or "") + " " + str(row.get("excerpt") or ""))


def clean_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create analysis-only normalized records while preserving originals."""
    clean = []
    seen = set()
    for row in rows:
        title = normalized_text(row.get("title"))
        excerpt = normalized_text(row.get("excerpt"))
        body = (title + " " + excerpt).strip()
        if not body or len(body) < 12 or any(x in body.lower() for x in SPAM):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", body.lower()).strip()[:240]
        if key in seen:
            continue
        seen.add(key)
        clean.append({
            "source": str(row.get("source") or "Unknown"),
            "title": title or "Untitled",
            "excerpt": excerpt,
            "url": str(row.get("url") or ""),
            "published": str(row.get("published") or ""),
            "engagement": max(0, int(row.get("engagement") or 0)),
            "domain": _domain(str(row.get("url") or "")),
            "analysis_text": body,
        })
    return clean


def group_evidence(items: list[dict[str, Any]], threshold: float = 0.48) -> list[dict[str, Any]]:
    """Conservative weighted-term clustering; every retained record appears once."""
    if not items:
        return []
    texts = [str(x.get("analysis_text") or _record_text(x)) for x in items]
    vectors = _tfidf_vectors(texts)
    order = sorted(range(len(items)), key=lambda i: (items[i].get("engagement", 0), -i), reverse=True)
    groups: list[list[int]] = []
    centroids: list[dict[str, float]] = []
    for idx in order:
        best_i, best_score = -1, 0.0
        for gi, centroid in enumerate(centroids):
            score = _similarity(vectors[idx], centroid)
            if score > best_score:
                best_i, best_score = gi, score
        if best_i >= 0 and best_score >= threshold:
            groups[best_i].append(idx)
            members = groups[best_i]
            terms = Counter()
            for member in members:
                terms.update(vectors[member])
            centroids[best_i] = {k: v / len(members) for k, v in terms.items()}
        else:
            groups.append([idx])
            centroids.append(dict(vectors[idx]))
    result = []
    for members in groups:
        records = [items[i] for i in members]
        words = Counter(w for row in records for w in tokens(row.get("analysis_text", "")))
        label = records[0].get("title") or "Unlabelled theme"
        result.append({
            "label": str(label)[:120],
            "size": len(records),
            "sources": sorted({x["source"] for x in records}),
            "domains": sorted({x["domain"] for x in records if x["domain"]}),
            "keywords": [w for w, _ in words.most_common(8)],
            "evidence": records,
        })
    return sorted(result, key=lambda x: (x["size"], len(x["sources"])), reverse=True)


def _hit_count(records: list[dict[str, Any]], vocab: set[str]) -> int:
    return sum(bool(set(tokens(x.get("analysis_text", ""))) & vocab) for x in records)


def _counter_examples(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for row in records:
        words = set(tokens(row.get("analysis_text", "")))
        if (words & POSITIVE and words & (PAIN | NEGATIVE)) or words & {"solved", "resolved", "fixed"}:
            result.append({"source": row["source"], "title": row["title"], "url": row["url"],
                           "reason": "Possible positive outcome or resolved-pain counter-signal; inspect context."})
        if len(result) >= 5:
            break
    return result


def _monthly(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in records:
        raw = str(row.get("published") or "")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            counts[dt.strftime("%Y-%m")] += 1
        except (ValueError, TypeError):
            continue
    return dict(sorted(counts.items()))


def _score(group: dict[str, Any], total: int) -> dict[str, Any]:
    records = group["evidence"]
    size = len(records)
    sources = len(group["sources"])
    domains = len(group["domains"])
    pain = _hit_count(records, PAIN)
    payment = _hit_count(records, PAY)
    solutions = _hit_count(records, SOLUTION)
    frequency = min(25.0, round(size / max(1, total) * 100, 1))
    problem = round(min(25.0, pain / max(1, size) * 25), 1)
    monetization = round(min(25.0, payment / max(1, size) * 25), 1)
    source_coverage = round(min(25.0, sources * 5 + domains * 2), 1)
    total_score = min(100, round(frequency + problem + monetization + source_coverage))
    confidence = min(100, round(min(size, 8) * 6 + sources * 9 + domains * 4))
    return {
        "frequency": frequency, "problem_evidence": problem,
        "monetization_language": monetization, "source_coverage": source_coverage,
        "score": total_score, "confidence": confidence,
        "pain_mentions": pain, "payment_mentions": payment,
        "solution_language": solutions,
        "counter_signals": _counter_examples(records),
        "competitor_coverage": "not_assessed",
    }


def _idea(group: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    theme = group["label"]
    audience = "The audience represented by the linked discussions; confirm its exact profile."
    return {
        "concept": "A focused product or workflow improvement addressing: " + theme,
        "audience_hypothesis": audience,
        "value_proposition": "Reduce the recurring effort, cost or frustration evidenced in this cluster.",
        "revenue_models_to_test": ["One-time purchase", "Freemium with a paid upgrade", "Usage-based pricing"],
        "mvp_scope": ["One narrow core workflow", "Simple onboarding", "A measurable before/after outcome"],
        "validation": [
            "Interview 5–8 people represented by the source discussions.",
            "Ask how they solve this today and what the workaround costs.",
            "Test a clickable prototype or landing page before building.",
            "Seek a real commitment such as a preorder, pilot or paid trial.",
        ],
        "caveat": "Generated as a hypothesis from public evidence, not a validated business recommendation.",
    }


def _gtm(group: dict[str, Any]) -> dict[str, Any]:
    channels = []
    for source in group["sources"]:
        channels.append({"channel": source, "reason": "Existing discussions were observed on this source.",
                         "test": "Contribute a useful answer or conduct opt-in customer interviews; do not spam."})
    return {
        "first_30_days": ["Interview target users", "Map current alternatives", "Test one narrow prototype"],
        "days_31_60": ["Run a small opt-in pilot", "Measure activation and repeat use", "Test willingness to pay"],
        "days_61_90": ["Keep, change or stop based on observed results", "Document acquisition cost and retention"],
        "channels_to_validate": channels,
    }


def _skeptic(group: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    risks = []
    if len(group["sources"]) < 2:
        risks.append("Evidence comes from fewer than two independent source platforms.")
    if len(group["domains"]) < 2:
        risks.append("Evidence has limited domain diversity.")
    if score["payment_mentions"] == 0:
        risks.append("No explicit payment or pricing language was detected.")
    if score["counter_signals"]:
        risks.append("Possible counter-signals or resolved complaints need manual review.")
    risks.append("Competitor coverage has not been collected in this scan.")
    risks.append("Public posts are not a representative sample of the full market.")
    return {"risks": risks, "decision": "validate" if score["score"] >= 45 else "collect_more_evidence",
            "pass_evidence_gate": len(risks) <= 2}


def run_analysis(topic: str, objective: str, signals: list[dict[str, Any]],
                 raw_records: int, source_errors: list[str] | None = None) -> dict[str, Any]:
    source_errors = source_errors or []
    evidence = clean_evidence(signals)
    groups = group_evidence(evidence)
    monthly = _monthly(evidence)
    month_keys = list(monthly)
    growth = None
    if len(month_keys) >= 2 and monthly[month_keys[-2]]:
        growth = round((monthly[month_keys[-1]] - monthly[month_keys[-2]]) / monthly[month_keys[-2]] * 100, 1)
    findings = []
    for idx, group in enumerate(groups, 1):
        score = _score(group, len(evidence))
        candidate = group["size"] >= 3 and score["problem_evidence"] >= 8
        findings.append({
            "id": "theme-" + str(idx), "title": group["label"],
            "evidence_count": group["size"], "sources": group["sources"],
            "source_domains": group["domains"], "keywords": group["keywords"],
            "score": score, "potential_gap": candidate,
            "gap_status": "candidate_needs_competitor_research" if candidate else "insufficient_evidence",
            "idea": _idea(group, score), "go_to_market": _gtm(group),
            "skeptic_review": _skeptic(group, score),
            "evidence": [{"source": x["source"], "title": x["title"], "url": x["url"],
                          "excerpt": x["excerpt"][:320], "published": x["published"]}
                         for x in group["evidence"][:20]],
        })
    findings.sort(key=lambda x: (x["potential_gap"], x["score"]["score"]), reverse=True)
    pain_count = _hit_count(evidence, PAIN)
    payment_count = _hit_count(evidence, PAY)
    sources = sorted({x["source"] for x in evidence})
    domains = sorted({x["domain"] for x in evidence if x["domain"]})
    counter_count = sum(len(x["score"]["counter_signals"]) for x in findings)
    confidence = min(100, round(min(len(evidence), 10) * 5 + len(sources) * 10 + min(len(domains), 5) * 3))
    stages = [
        {"id": "intake", "status": "complete", "detail": "Topic and research objective captured."},
        {"id": "source_discovery", "status": "complete", "detail": f"{len(sources)} source types returned evidence."},
        {"id": "evidence_cleaning", "status": "complete", "detail": f"{len(evidence)} normalized records retained; originals remain linked."},
        {"id": "theme_discovery", "status": "complete", "detail": f"{len(groups)} themes grouped with weighted local text similarity."},
        {"id": "voice_of_customer", "status": "complete", "detail": f"{pain_count} records contain problem language."},
        {"id": "monetization_review", "status": "complete", "detail": f"{payment_count} records contain payment or pricing language."},
        {"id": "counterevidence_review", "status": "complete", "detail": f"{counter_count} possible counter-signals flagged for human review."},
        {"id": "competitor_analysis", "status": "not_run", "detail": "Dedicated competitor collection is not available in this scan; no gap is confirmed."},
        {"id": "idea_design", "status": "complete", "detail": "Concepts and MVP hypotheses generated from evidence themes."},
        {"id": "feasibility_scoring", "status": "complete", "detail": "Transparent directional score; not a market-size or revenue estimate."},
        {"id": "skeptic_review", "status": "complete", "detail": "Evidence limits and contradictory signals attached to each theme."},
        {"id": "go_to_market", "status": "hypothesis", "detail": "Suggested validation sequence; channels are not proven acquisition sources."},
    ]
    if source_errors:
        stages.insert(1, {"id": "source_health", "status": "partial", "detail": "; ".join(source_errors)[:700]})
    opportunities = [x for x in findings if x["potential_gap"]]
    return {
        "schema_version": "cashforge-intelligence-v2",
        "topic": topic, "objective": objective,
        "pipeline": stages,
        "evidence": {
            "raw_records": raw_records, "retained_records": len(evidence),
            "independent_sources": len(sources), "unique_domains": len(domains),
            "problem_language_records": pain_count, "payment_language_records": payment_count,
            "counter_signal_count": counter_count, "confidence": confidence,
        },
        "trends": {"mentions_by_month": monthly, "month_over_month_change_pct": growth,
                   "interpretation": "Insufficient dated history" if growth is None else "Descriptive change between the two latest months; not a forecast."},
        "opportunities": findings[:20],
        "decision": {
            "status": "candidate_opportunities" if opportunities else "more_evidence_needed",
            "summary": ("Potential problem clusters were found. Competitor coverage and willingness to pay still need independent validation."
                        if opportunities else "The current evidence is not strong enough to call a market gap. Narrow the question or collect more independent evidence."),
        },
        "limitations": [
            "Similarity uses a local TF-IDF-style text model, not a neural embedding model.",
            "Public discussion volume does not prove market demand or willingness to pay.",
            "Competitor coverage was not assessed in this run.",
            "Opportunity scores are directional research aids, not forecasts.",
            "Growth is reported only when at least two dated months are represented.",
        ],
    }


def build_markdown_report(analysis: dict[str, Any], run: dict[str, Any]) -> str:
    lines = [
        "# CashForge research report", "", f"**Topic:** {analysis.get('topic','')}",
        f"**Objective:** {analysis.get('objective','')}", f"**Run:** {run.get('created_at','')}", "",
        "## Decision", "", analysis.get("decision", {}).get("summary", ""), "",
        "## Evidence overview", "",
    ]
    evidence = analysis.get("evidence", {})
    for key, label in [("raw_records", "Raw records"), ("retained_records", "Retained records"),
                       ("independent_sources", "Source types"), ("unique_domains", "Domains"),
                       ("problem_language_records", "Problem-language records"),
                       ("payment_language_records", "Payment-language records"), ("confidence", "Evidence confidence")]:
        lines.append(f"- {label}: {evidence.get(key, 0)}")
    lines.extend(["", "## Opportunity themes", ""])
    for item in analysis.get("opportunities", []):
        score = item["score"]
        lines.extend([f"### {item['title']}", "", f"- Evidence: {item['evidence_count']} mentions across {', '.join(item['sources'])}",
                      f"- Directional score: {score['score']}/100; confidence indicator: {score['confidence']}/100",
                      f"- Problem evidence: {score['problem_evidence']}/25; payment language: {score['monetization_language']}/25",
                      f"- Status: {item['gap_status']}", "", "#### Concept hypothesis", item["idea"]["concept"],
                      "", "#### Validation plan"])
        lines.extend(f"- {step}" for step in item["idea"]["validation"])
        lines.extend(["", "#### Risks"])
        lines.extend(f"- {risk}" for risk in item["skeptic_review"]["risks"])
        lines.extend(["", "#### Evidence"])
        lines.extend(f"- [{row['title']}]({row['url']}) — {row['source']}" for row in item["evidence"])
        lines.append("")
    lines.extend(["## Research limitations", ""])
    lines.extend(f"- {x}" for x in analysis.get("limitations", []))
    return "\n".join(lines).strip() + "\n"


def build_html_report(analysis: dict[str, Any], run: dict[str, Any]) -> str:
    md = build_markdown_report(analysis, run)
    escaped = html.escape(md)
    return ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>CashForge research report</title><style>body{max-width:900px;margin:40px auto;padding:0 20px;background:#10110f;color:#eef2e6;font:16px/1.7 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#d7e4c3;background:#191d16;padding:24px;border-radius:12px}</style>"
            "<body><h1>CashForge research report</h1><pre>" + escaped + "</pre></body></html>")
