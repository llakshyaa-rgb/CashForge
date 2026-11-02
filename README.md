# CashForge

CashForge is a private-first, mobile-friendly opportunity research workspace. The first module is an evidence-led Trend Radar: collect public signals, review source links, compare supporting and opposing evidence, and save research runs locally.

## Current scope

- Local web dashboard designed for phone screens.
- Python standard-library server; no npm, database service, or paid hosting required.
- Public-source discovery from Hacker News Algolia, Reddit's public JSON endpoints, and Google News RSS.
- SQLite research library preserving past topics, objectives, selected source combinations, and results across refreshes.
- Multi-angle topic discovery and grouped near-duplicate reporting, with representative links to inspect matching mentions.
- Local TF-IDF-style text weighting and conservative evidence clustering; grouped source links remain available to analysis.
- Voice-of-customer indicators for recurring pain, payment language, solution language, and possible counter-signals.
- Historical month buckets when source timestamps are available; changes are descriptive, never forecasts.
- Per-theme opportunity hypotheses, audience and value-proposition hypotheses, revenue models to test, MVP scope, validation experiments, and a cautious 30/60/90-day go-to-market outline.
- Skeptic review that flags thin source diversity, absent payment evidence, counter-signals, and missing competitor research.
- Transparent opportunity scoring with separate evidence confidence and explicit limitations.
- Markdown, standalone HTML, and JSON report exports for each saved run.
- Optional OpenRouter AI analyst: evidence-grounded chat and deeper analysis, with source IDs and explicit unknowns.
- Optional semantic embeddings for evidence clustering when configured and supported; local TF-IDF fallback remains available.
- Competitor discovery workflow using public Hacker News and Google News search, with explicit unverified-lead warnings.
- Persistent topic monitors, repeat scans while the local server is running, and run-to-run comparison API.
- Cross-run research memory: recurring themes and prior evidence are stored locally and supplied to the AI analyst for the same normalized topic.
- Bounded competitor/alternative page inspection: fetches a small sample of public HTTPS HTML pages and extracts price-like strings and feature-page clues for manual verification.
- Customer-language sentiment hints (transparent keyword heuristics, not a trained sentiment model).
- Validation evidence report with payment-language leads and concrete interview, concierge-pilot, price-commitment and retention experiments.
- Source-level inspection, filters, export, and repeatable topic studies.
- Clear distinction between observed signals and hypotheses.

This is the first CashForge module, not an automated money-making or revenue-prediction system. It does not create products, publish content, spend money, or guarantee demand or income. Collection is read-only and bounded; respect source terms, rate limits, and applicable law.

## Run locally (Termux / Linux / macOS)

```bash
git clone https://github.com/llakshyaa-rgb/CashForge.git
cd CashForge
python server.py
```

CashForge uses port `8766` by default (Purffle can keep using `8765`). Open `http://127.0.0.1:8766` on the same device. Keep the terminal session running. No API key is required for the built-in public-source collectors or local analysis. Optional AI keys can be added in the dashboard's **Settings** button; OpenRouter and OpenAI are supported.

## AI provider settings

Open **Settings** in the dashboard and choose OpenRouter or OpenAI. Paste your API key, optionally change the chat and embedding model names, and save. CashForge stores the key in `data/provider_settings.json` on the device with owner-only file permissions where supported. The file is ignored by Git. The key is never returned to the browser after saving. Remove it from the same Settings panel when no longer needed. API calls are sent to the selected provider and may incur charges; review that provider's terms and pricing.

The app can still run without a key using local analysis. Embeddings are optional and fall back to local TF-IDF if the provider/model does not support them.

## Research memory, competitor inspection and validation\n\nEvery opened research run is indexed in local SQLite memory by normalized topic. The AI chat receives up to eight prior snapshots for the same topic, including recurring themes. This is a retrieval aid, not an all-knowing memory system; near-matching topics are not automatically merged.\n\nCompetitor page inspection uses a small bounded sample of public HTTPS HTML pages from search leads. Extracted price-like strings and feature terms can be stale, misleading or unrelated to an actual plan. Treat them as leads and open original pages before making decisions. Sentiment is a transparent keyword heuristic and can misread context, sarcasm and negation.\n\nValidation reports surface payment-language mentions but do not establish that a buyer paid for the proposed product. The included experiments are suggestions; users must conduct interviews, pilots and price tests themselves.\n\n## Monitoring behavior\n\nTracked topics are scanned immediately and then at the selected interval while the local CashForge server process is running. If Termux kills the process, the device reboots, or connectivity is unavailable, scheduled scans pause; this is not a cloud scheduler. Compare runs using `/api/compare/OLD_ID/NEW_ID`.\n\nCompetitor discovery collects search leads, not verified competitor profiles. Pricing, features, reviews and customer complaints still require opening and validating original pages.\n\n## How it works

1. Enter a topic and select a research objective.
2. CashForge searches up to seven related query angles per selected source, with bounded requests (up to 35 Hacker News / Google News items per angle and up to 50 Reddit items per angle, subject to source limits).
3. Exact URL duplicates and title-similar records are grouped rather than silently discarded; counts and representative links remain visible. All research runs are stored in a local SQLite database.
4. Each signal retains its original URL, source, timestamp, and available engagement metadata.
5. CashForge normalizes the evidence for analysis, groups related text conservatively, and keeps the original source records linked.
6. It analyses pain language, payment language, possible counter-signals, dated mention history, and directional opportunity scores.
7. For each theme it drafts a solution concept, validation experiments, an MVP outline, and a go-to-market hypothesis. A skeptic review records missing evidence and risks.
8. Competitor coverage remains explicitly unassessed until a dedicated competitor-source workflow is completed. No theme is presented as a confirmed market gap.
9. Open the original sources, inspect the limitations, and use the Markdown, HTML, or JSON report export for each saved run.

## Privacy and safety

- Research data and saved research configurations stay in `data/cashforge.db` on the device.
- Refreshing opens a fresh blank research screen; use the Research Library to reopen previous runs.
- The server binds to loopback by default; it is not exposed to the public internet.
- No cookies, account passwords, browser sessions, or tokens are collected.
- Do not commit your local database or private research exports.
- Stop collection if a source blocks access or signals rate limiting.

## Tests

Run the standard-library test suite with:

```bash
python -m unittest discover -s tests -v
```

## Report exports

For a saved run with ID `N`, open `/api/run/N/report.md`, `/api/run/N/report.html`, or `/api/run/N/report.json` on the local server.

## Project status

CashForge now includes a local opportunity-analysis and validation-hypothesis layer. AI chat and deep analysis, bounded competitor lead discovery, optional embeddings, local topic monitors and run comparisons are now integrated. Automated customer interviews, paid demand tests, reliable cross-platform source coverage, and operation while the phone/server is off remain limitations. Competitor page extraction and sentiment are intentionally labelled as unverified/heuristic.

## Inspiration and attribution

Selected workflow ideas were informed by two MIT-licensed projects and one project with no declared licence. CashForge does not copy source code from the unlicensed project. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the repository-by-repository review and attribution.
