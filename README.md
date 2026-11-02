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
- Source-level inspection, filters, export, and repeatable topic studies.
- Clear distinction between observed signals and hypotheses.

This is the first CashForge module, not an automated money-making or revenue-prediction system. It does not create products, publish content, spend money, or guarantee demand or income. Collection is read-only and bounded; respect source terms, rate limits, and applicable law.

## Run locally (Termux / Linux / macOS)

```bash
git clone https://github.com/llakshyaa-rgb/CashForge.git
cd CashForge
python server.py
```

CashForge uses port `8766` by default (Purffle can keep using `8765`). Open `http://127.0.0.1:8766` on the same device. Keep the terminal session running. No API key is required for the built-in public-source collectors or local analysis. Optional AI requires an OpenRouter API key.

## Optional AI setup (Termux)\n\nCashForge works without AI. To enable the analyst, set your OpenRouter key in the Termux session before starting the server:\n\n```bash\nexport OPENROUTER_API_KEY='YOUR_OPENROUTER_KEY'\n# Optional model overrides\nexport CASHFORGE_AI_MODEL='openai/gpt-oss-20b:free'\nexport CASHFORGE_EMBED_MODEL='openai/text-embedding-3-small'\npython server.py\n```\n\nThe key is read only by the local Python server; it is never sent to the browser or stored in SQLite. Model availability, pricing and embedding support depend on the provider. If embeddings are unavailable, clustering falls back to local TF-IDF. Check your provider's current model and pricing before use. Do not commit keys or put them in dashboard fields.\n\n## Monitoring behavior\n\nTracked topics are scanned immediately and then at the selected interval while the local CashForge server process is running. If Termux kills the process, the device reboots, or connectivity is unavailable, scheduled scans pause; this is not a cloud scheduler. Compare runs using `/api/compare/OLD_ID/NEW_ID`.\n\nCompetitor discovery collects search leads, not verified competitor profiles. Pricing, features, reviews and customer complaints still require opening and validating original pages.\n\n## How it works

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

CashForge now includes a local opportunity-analysis and validation-hypothesis layer. AI chat and deep analysis, bounded competitor lead discovery, optional embeddings, local topic monitors and run comparisons are now integrated. Competitor verification, automatic operation while the phone/server is off, reliable cross-platform source coverage, and actual market-demand proof remain limitations.

## Inspiration and attribution

Selected workflow ideas were informed by two MIT-licensed projects and one project with no declared licence. CashForge does not copy source code from the unlicensed project. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the repository-by-repository review and attribution.
